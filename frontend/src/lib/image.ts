// Phone photos are often 3-8 MB. Shrink them in the browser before sending:
// faster uploads, and fewer tokens for Gemini to read. 1280px is plenty to
// recognise ingredients.

const MAX_SIDE = 1280;

export async function shrinkImage(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas.toDataURL("image/jpeg", 0.85); // "data:image/jpeg;base64,..."
}
