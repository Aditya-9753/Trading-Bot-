import { frac, money, pct, score, signedMoney, tone } from "../lib/format";

describe("format", () => {
  it("formats rupees in the Indian system", () => {
    expect(money(1234567.5)).toBe("₹12,34,567.50");
    expect(money(null)).toBe("—");
  });
  it("signs money and percentages with a real minus sign", () => {
    expect(signedMoney(-250)).toBe("−₹250.00");
    expect(signedMoney(250)).toBe("+₹250.00");
    expect(pct(-1.234)).toBe("−1.23%");
    expect(frac(0.034, 1, true)).toBe("+3.4%");
  });
  it("formats signal scores and tones", () => {
    expect(score(0.5)).toBe("+0.50");
    expect(score(-0.25)).toBe("−0.25");
    expect(tone(-1)).toBe("loss");
    expect(tone(0)).toBe("");
  });
});
