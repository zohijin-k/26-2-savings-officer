/** Fit the widest rotated page without enlarging small originals. Zoom is applied afterwards. */
export function fitDocumentScale(
  sizes: readonly { width: number; height: number }[],
  availableWidth: number,
  rotation: number,
): number {
  const turned = rotation === 90 || rotation === 270
  const widest = Math.max(0, ...sizes.map((size) => turned ? size.height : size.width))
  return availableWidth > 0 && widest > 0 ? Math.min(1, availableWidth / widest) : 1
}
