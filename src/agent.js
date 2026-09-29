/* エージェントのロジック本体。UI から切り離した純粋関数にしてテストしやすくする。 */

export function reply(input) {
  const text = String(input ?? "").trim();
  if (text === "") return "何か入力してください。";
  return `「${text}」を受け取りました。`;
}
