import { describe, it, expect } from "vitest";
import { reply } from "../src/agent.js";

describe("reply", () => {
  it("入力をそのまま返す", () => {
    expect(reply("こんにちは")).toBe("「こんにちは」を受け取りました。");
  });

  it("前後の空白は無視する", () => {
    expect(reply("  hi  ")).toBe("「hi」を受け取りました。");
  });

  it("空入力には入力を促す", () => {
    expect(reply("")).toBe("何か入力してください。");
    expect(reply(undefined)).toBe("何か入力してください。");
  });
});
