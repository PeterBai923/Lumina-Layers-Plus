import torch
from typing import Optional


class GPUDeviceManager:
    _instance: Optional['GPUDeviceManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'GPUDeviceManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None
        cls._initialized = False

    def __init__(self):
        if self._initialized:
            return

        self._cuda_available = self._check_cuda_available()
        self._device = self._select_device() if self._cuda_available else None
        self._initialized = True

    def _check_cuda_available(self) -> bool:
        if not torch.cuda.is_available():
            return False

        try:
            device = torch.device('cuda:0')
            test_tensor = torch.zeros(1, 1, device=device)

            result = torch.cdist(test_tensor, test_tensor)
            del test_tensor, result

            return True
        except (RuntimeError, torch.cuda.OutOfMemoryError):
            return False

    def _select_device(self) -> torch.device:
        if not self._cuda_available:
            raise RuntimeError("CUDA is not available")

        return torch.device('cuda:0')

    def is_cuda_available(self) -> bool:
        return self._cuda_available

    def get_device(self) -> torch.device:
        if not self._cuda_available:
            raise RuntimeError("CUDA is not available")
        return self._device

    def clear_cache(self):
        if self._cuda_available:
            torch.cuda.empty_cache()

    def get_memory_info(self) -> dict:
        if not self._cuda_available:
            return {'total': 0, 'reserved': 0, 'allocated': 0, 'available': 0}

        total = torch.cuda.get_device_properties(0).total_memory
        reserved = torch.cuda.memory_reserved(0)
        allocated = torch.cuda.memory_allocated(0)

        return {
            'total': total,
            'reserved': reserved,
            'allocated': allocated,
            'available': total - reserved
        }

    def calculate_batch_size(
        self,
        n_elements: int,
        element_size_bytes: float,
        operation_type: str = 'distance'
    ) -> int:
        if not self._cuda_available:
            return min(50_000, n_elements)

        try:
            free_memory = torch.cuda.mem_get_info()[0]

            max_batch = int((free_memory * 0.4) / element_size_bytes)

            batch_size = max(10_000, min(max_batch, n_elements))

            return batch_size

        except Exception:
            return min(50_000, n_elements)

    def should_use_gpu(
        self,
        n_elements: int,
        threshold: Optional[int] = None
    ) -> bool:
        if not self._cuda_available:
            return False

        if threshold is None:
            try:
                available_mb = torch.cuda.mem_get_info()[0] / (1024**2)

                if available_mb > 8000:
                    threshold = 100_000_000  # 400MB equivalent
                elif available_mb > 4000:
                    threshold = 50_000_000
                else:
                    threshold = 10_000_000
            except Exception:
                threshold = 10_000_000

        return n_elements >= threshold

    def get_batch_size_for_distance_matrix(
        self,
        n_pixels: int,
        n_centers: int,
        feature_dim: int = 3
    ) -> int:
        # Memory per pixel: n_centers * 4 (distance) + feature_dim * 4 (features)
        bytes_per_pixel = (n_centers * 4 + feature_dim * 4) * 1.2
        return self.calculate_batch_size(n_pixels, bytes_per_pixel, 'distance')

    def get_batch_size_for_color_mapping(
        self,
        n_queries: int,
        n_lut: int
    ) -> int:
        bytes_per_query = (n_lut * 4 + 8) * 1.5
        return self.calculate_batch_size(n_queries, bytes_per_query, 'mapping')

    def get_device_info(self) -> dict:
        """
        Get GPU device information.

        Returns:
            dict: Device information including:
                - device: Device type string
                - cuda_available: Whether CUDA is available
                - gpu_enabled: Whether GPU is enabled
                - gpu_name: GPU device name (if available)
                - gpu_memory: Total GPU memory in GB (if available)
        """
        if not self._cuda_available:
            return {
                'device': 'CPU',
                'cuda_available': False,
                'gpu_enabled': False,
                'gpu_name': None,
                'gpu_memory': 0
            }

        return {
            'device': 'GPU (CUDA)',
            'cuda_available': True,
            'gpu_enabled': True,
            'gpu_name': torch.cuda.get_device_name(),
            'gpu_memory': torch.cuda.get_device_properties(0).total_memory / (1024**3)
        }
