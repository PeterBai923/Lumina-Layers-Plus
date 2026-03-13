import { useEffect } from "react";
import { useFiveColorStore } from "../stores/fiveColorStore";
import { useConverterStore } from "../stores/converterStore";
import Dropdown from "./ui/Dropdown";
import Button from "./ui/Button";
import { useI18n } from "../i18n/context";

export default function FiveColorQueryPanel() {
  const { t } = useI18n();
  const {
    lutName,
    baseColors,
    selectedIndices,
    queryResult,
    isLoading,
    error,
    loadBaseColors,
    addSelection,
    removeLastSelection,
    clearSelection,
    reverseSelection,
    submitQuery,
    clearError,
  } = useFiveColorStore();

  const lutList = useConverterStore((s) => s.lutList);
  const fetchLutList = useConverterStore((s) => s.fetchLutList);

  useEffect(() => {
    if (lutList.length === 0) {
      void fetchLutList();
    }
  }, []);

  const handleLutChange = (name: string) => {
    if (name) {
      clearError();
      void loadBaseColors(name);
    }
  };

  const hasSelection = selectedIndices.length > 0;
  const isFull = selectedIndices.length === 5;

  return (
    <div className="flex-1 h-full overflow-y-auto bg-gray-800 p-6">
      <div className="max-w-4xl mx-auto flex gap-6">
        {/* Left column: LUT selector, action buttons, result */}
        <div className="w-64 flex flex-col gap-4 shrink-0">
          <Dropdown
            label={t("five_color_lut_label")}
            value={lutName}
            options={lutList.map((n) => ({ label: n, value: n }))}
            onChange={handleLutChange}
            placeholder={t("five_color_lut_placeholder")}
          />

          {/* Action buttons */}
          <div className="flex flex-col gap-2">
            <Button
              label={t("five_color_clear")}
              variant="secondary"
              onClick={clearSelection}
              disabled={!hasSelection}
            />
            <Button
              label={t("five_color_undo")}
              variant="secondary"
              onClick={removeLastSelection}
              disabled={!hasSelection}
            />
            <Button
              label={t("five_color_reverse")}
              variant="secondary"
              onClick={reverseSelection}
              disabled={!isFull}
            />
            <Button
              label={t("five_color_query")}
              variant="primary"
              onClick={() => void submitQuery()}
              disabled={!isFull || isLoading}
              loading={isLoading}
            />
          </div>

          {/* Error display */}
          {error && (
            <div className="flex items-start gap-2 rounded-md bg-red-900/30 border border-red-700 p-3 text-xs text-red-300">
              <span>{error}</span>
              <button
                onClick={clearError}
                className="ml-auto shrink-0 text-red-400 hover:text-red-200"
                aria-label={t("five_color_close_error")}
              >
                ×
              </button>
            </div>
          )}

          {/* Result display */}
          {queryResult && (
            <div className="flex flex-col gap-2 rounded-md border border-gray-600 p-3">
              {queryResult.found ? (
                <>
                  <div
                    className="w-full h-20 rounded-md border border-gray-500"
                    style={{ backgroundColor: queryResult.result_hex ?? undefined }}
                    aria-label={t("five_color_result_color").replace("{hex}", queryResult.result_hex ?? "")}
                  />
                  <p className="text-sm text-gray-200">
                    {t("five_color_result_hex")}: {queryResult.result_hex}
                  </p>
                  <p className="text-sm text-gray-200">
                    {t("five_color_result_rgb")}: {queryResult.result_rgb?.join(", ")}
                  </p>
                  <p className="text-xs text-gray-400">
                    {t("five_color_result_row")}: {queryResult.row_index}
                  </p>
                </>
              ) : (
                <p className="text-sm text-yellow-400">{t("five_color_not_found")}</p>
              )}
            </div>
          )}
        </div>

        {/* Right column: color grid + selection sequence */}
        <div className="flex-1 flex flex-col gap-4">
          {/* Selection sequence: 5 circular slots with arrows */}
          <div className="flex items-center gap-1 justify-center py-2">
            {Array.from({ length: 5 }).map((_, i) => {
              const colorIndex = selectedIndices[i];
              const color = colorIndex !== undefined
                ? baseColors.find((c) => c.index === colorIndex)
                : null;
              return (
                <div key={i} className="flex items-center gap-1">
                  <div
                    className="w-10 h-10 rounded-full border-2 border-gray-500 flex items-center justify-center text-xs text-gray-400"
                    style={color ? { backgroundColor: color.hex, borderColor: color.hex } : undefined}
                    aria-label={color ? t("five_color_selected").replace("{n}", String(i + 1)).replace("{name}", color.name) : t("five_color_slot_empty").replace("{n}", String(i + 1))}
                  >
                    {!color && (i + 1)}
                  </div>
                  {i < 4 && <span className="text-gray-500 text-sm">→</span>}
                </div>
              );
            })}
          </div>

          {/* Base color grid */}
          {baseColors.length > 0 && (
            <div className="grid grid-cols-4 gap-2">
              {baseColors.map((color) => (
                <button
                  key={color.index}
                  onClick={() => addSelection(color.index)}
                  disabled={isFull}
                  className="flex flex-col items-center gap-1 rounded-md border border-gray-600 p-2 hover:border-blue-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label={t("five_color_select_color").replace("{name}", color.name).replace("{hex}", color.hex)}
                >
                  <div
                    className="w-10 h-10 rounded-md border border-gray-500"
                    style={{ backgroundColor: color.hex }}
                  />
                  <span className="text-xs text-gray-300 truncate w-full text-center">
                    {color.name}
                  </span>
                  <span className="text-xs text-gray-500">{color.hex}</span>
                </button>
              ))}
            </div>
          )}

          {baseColors.length === 0 && lutName && !isLoading && (
            <p className="text-sm text-gray-500 text-center py-8">
              {t("five_color_no_base_colors")}
            </p>
          )}

          {baseColors.length === 0 && !lutName && (
            <p className="text-sm text-gray-500 text-center py-8">
              {t("five_color_select_lut_first")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
