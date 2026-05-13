import torch
import numpy as np
from typing import Tuple, Optional
from core.utils.gpu_device import GPUDeviceManager


class CUDAKMeansPlusPlus:
    def __init__(self, device_manager: Optional[GPUDeviceManager] = None):
        self.device_manager = device_manager or GPUDeviceManager()

    def _should_use_batch_processing(self, N: int, k: int) -> bool:
        """Check if batch processing is needed based on GPU memory."""
        return self.device_manager.should_use_gpu(N * k)

    def _compute_distances_with_amp(
        self, X: torch.Tensor, centers: torch.Tensor
    ) -> torch.Tensor:
        with torch.cuda.amp.autocast():
            distances = torch.cdist(X, centers)

        return distances.float()

    def _lloyd_iteration_minibatch(
        self,
        X: torch.Tensor,
        centers: torch.Tensor,
        max_iter: int,
        tol: float,
        batch_size: int = 10000,
    ) -> Tuple[torch.Tensor, float]:
        N, D = X.shape
        k = centers.shape[0]
        device = X.device

        centers_sum = torch.zeros_like(centers)
        centers_count = torch.zeros(k, device=device, dtype=torch.long)

        for iteration in range(max_iter):
            indices = torch.randint(0, N, (batch_size,), device=device)
            X_batch = X[indices]

            distances = torch.cdist(X_batch, centers)
            labels_batch = distances.argmin(dim=1)

            torch.scatter_reduce(
                centers_sum,
                dim=0,
                index=labels_batch.unsqueeze(1).expand(-1, D),
                src=X_batch,
                reduce="sum",
                include_self=True,
            )

            ones = torch.ones(batch_size, device=device, dtype=torch.long)
            torch.scatter_reduce(
                centers_count,
                dim=0,
                index=labels_batch,
                src=ones,
                reduce="sum",
                include_self=True,
            )

            new_centers = torch.zeros_like(centers)
            mask = centers_count > 0
            new_centers[mask] = (
                centers_sum[mask] / centers_count[mask].unsqueeze(1).float()
            )

            empty_count = (~mask).sum().item()
            if empty_count > 0:
                random_indices = torch.randint(0, N, (empty_count,), device=device)
                new_centers[~mask] = X[random_indices]

            center_shift = torch.norm(new_centers - centers, dim=1).max()
            centers = new_centers

            if center_shift < tol:
                break

        labels = self._assign_clusters(X, centers)
        inertia = self._compute_inertia(X, centers, labels)

        return centers, inertia

    def fit(
        self,
        pixels: np.ndarray,
        k: int,
        max_iter: int = 100,
        tol: float = 1e-4,
        n_init: int = 10,
        seed: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> np.ndarray:
        if not self.device_manager.is_cuda_available():
            raise RuntimeError("CUDA is not available")

        device = self.device_manager.get_device()

        X = torch.from_numpy(pixels).to(device, non_blocking=True)

        N = X.shape[0]

        use_minibatch = N > 100_000
        if batch_size is None and use_minibatch:
            batch_size = min(10000, N // 10)

        best_centers = None
        best_inertia = float("inf")

        for init_idx in range(n_init):
            if seed is not None:
                torch.manual_seed(seed + init_idx)

            try:
                centers = self._initialize_centers_kmeans_plus_plus(X, k)

                if use_minibatch:
                    centers, inertia = self._lloyd_iteration_minibatch(
                        X, centers, max_iter, tol, batch_size
                    )
                else:
                    centers, inertia = self._lloyd_iteration(X, centers, max_iter, tol)

                if inertia < best_inertia:
                    best_inertia = inertia
                    best_centers = centers

            except torch.cuda.OutOfMemoryError:
                self.device_manager.clear_cache()
                if init_idx == n_init - 1 and best_centers is None:
                    raise RuntimeError("GPU out of memory during K-Means")
                continue

        result = best_centers.cpu().numpy()

        del X
        self.device_manager.clear_cache()

        return result

    def _initialize_centers_kmeans_plus_plus(
        self, X: torch.Tensor, k: int
    ) -> torch.Tensor:
        N, D = X.shape
        device = X.device

        centers = torch.zeros(k, D, device=device, dtype=X.dtype)

        idx = torch.randint(0, N, (1,), device=device)
        centers[0] = X[idx]

        min_distances = torch.full((N,), float("inf"), device=device, dtype=X.dtype)

        for i in range(1, k):
            new_center = centers[i - 1 : i]
            dist_to_new = torch.cdist(X, new_center).squeeze() ** 2

            min_distances = torch.minimum(min_distances, dist_to_new)

            probs = min_distances / min_distances.sum()

            idx = torch.multinomial(probs, 1)
            centers[i] = X[idx]

        return centers

    def _compute_min_distances(
        self, X: torch.Tensor, centers: torch.Tensor
    ) -> torch.Tensor:
        N = X.shape[0]
        k = centers.shape[0]

        if not self._should_use_batch_processing(N, k):
            distances = torch.cdist(X, centers)
            min_distances_sq = distances.min(dim=1)[0] ** 2
        else:
            feature_dim = X.shape[1]
            batch_size = self.device_manager.get_batch_size_for_distance_matrix(N, k, feature_dim)
            min_distances_sq = torch.zeros(N, device=X.device, dtype=X.dtype)

            for start in range(0, N, batch_size):
                end = min(start + batch_size, N)
                X_batch = X[start:end]

                distances_batch = torch.cdist(X_batch, centers)
                min_distances_sq[start:end] = distances_batch.min(dim=1)[0] ** 2

        return min_distances_sq

    def _update_centers_vectorized(
        self, X: torch.Tensor, labels: torch.Tensor, k: int
    ) -> torch.Tensor:
        N, D = X.shape
        device = X.device

        new_centers = torch.zeros(k, D, device=device, dtype=X.dtype)
        counts = torch.zeros(k, device=device, dtype=torch.long)

        torch.scatter_reduce(
            new_centers,
            dim=0,
            index=labels.unsqueeze(1).expand(-1, D),
            src=X,
            reduce="sum",
            include_self=False,
        )

        ones = torch.ones(N, device=device, dtype=torch.long)
        torch.scatter_reduce(
            counts, dim=0, index=labels, src=ones, reduce="sum", include_self=False
        )

        mask = counts > 0
        new_centers[mask] = new_centers[mask] / counts[mask].unsqueeze(1).float()

        empty_count = (~mask).sum().item()
        if empty_count > 0:
            random_indices = torch.randint(0, N, (empty_count,), device=device)
            new_centers[~mask] = X[random_indices]

        return new_centers

    def _lloyd_iteration(
        self, X: torch.Tensor, centers: torch.Tensor, max_iter: int, tol: float
    ) -> Tuple[torch.Tensor, float]:
        k = centers.shape[0]
        N = X.shape[0]

        for iteration in range(max_iter):
            if not self._should_use_batch_processing(N, k):
                distances = torch.cdist(X, centers)
                labels = distances.argmin(dim=1)
                min_distances = distances.min(dim=1)[0]
            else:
                feature_dim = X.shape[1]
                batch_size = self.device_manager.get_batch_size_for_distance_matrix(
                    N, k, feature_dim
                )
                labels = torch.zeros(N, device=X.device, dtype=torch.long)
                min_distances_list = []

                for start in range(0, N, batch_size):
                    end = min(start + batch_size, N)
                    X_batch = X[start:end]
                    dist_batch = torch.cdist(X_batch, centers)
                    labels[start:end] = dist_batch.argmin(dim=1)
                    min_distances_list.append(dist_batch.min(dim=1)[0])

                min_distances = torch.cat(min_distances_list)

            new_centers = self._update_centers_vectorized(X, labels, k)

            center_shift = torch.norm(new_centers - centers, dim=1).max()
            centers = new_centers

            if center_shift < tol:
                break

        inertia = (min_distances**2).sum().item()

        return centers, inertia

    def _assign_clusters(self, X: torch.Tensor, centers: torch.Tensor) -> torch.Tensor:
        N = X.shape[0]
        k = centers.shape[0]

        if not self._should_use_batch_processing(N, k):
            distances = torch.cdist(X, centers)
            labels = distances.argmin(dim=1)
        else:
            feature_dim = X.shape[1]
            batch_size = self.device_manager.get_batch_size_for_distance_matrix(N, k, feature_dim)
            labels = torch.zeros(N, device=X.device, dtype=torch.long)

            for start in range(0, N, batch_size):
                end = min(start + batch_size, N)
                X_batch = X[start:end]

                distances_batch = torch.cdist(X_batch, centers)
                labels[start:end] = distances_batch.argmin(dim=1)

        return labels

    def _compute_inertia(
        self, X: torch.Tensor, centers: torch.Tensor, labels: torch.Tensor
    ) -> float:
        assigned_centers = centers[labels]
        sq_distances = ((X - assigned_centers) ** 2).sum(dim=1)
        inertia = sq_distances.sum().item()

        return inertia
