import { fireEvent, render, screen } from "@testing-library/react";
import SignalGauge from "../components/SignalGauge";
import { Badge, Tabs } from "../components/ui";
import { Contributions } from "../components/charts";

describe("SignalGauge", () => {
  it("names the zone for a value past the entry threshold", () => {
    render(<SignalGauge value={0.7} entry={0.55} exit={-0.25} action="BUY" />);
    expect(screen.getByText("Buy zone")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(/\+0\.70, Buy zone/);
  });
  it("shows the exit zone for longs", () => {
    render(<SignalGauge value={-0.3} entry={0.55} exit={-0.25} />);
    expect(screen.getByText("Exit zone for longs")).toBeInTheDocument();
  });
  it("handles missing data", () => {
    render(<SignalGauge value={null} entry={0.55} exit={-0.25} />);
    expect(screen.getByText("Not enough data")).toBeInTheDocument();
  });
  it("clamps out-of-range values", () => {
    render(<SignalGauge value={3} entry={0.55} exit={-0.25} />);
    expect(screen.getByText("+1.00")).toBeInTheDocument();
  });
});

describe("ui", () => {
  it("renders readable badge text", () => {
    render(<Badge value="HIGH_VOLATILITY" />);
    expect(screen.getByText("High volatility")).toBeInTheDocument();
  });
  it("switches tabs", () => {
    const onChange = vi.fn();
    render(<Tabs<"a" | "b"> value="a" onChange={onChange} options={[{ value: "a", label: "A" }, { value: "b", label: "B" }]} />);
    fireEvent.click(screen.getByRole("tab", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });
  it("draws contributions with signed values", () => {
    render(<Contributions values={{ trend: 0.3, reversion: -0.1 }} />);
    expect(screen.getByText("+0.30")).toBeInTheDocument();
    expect(screen.getByText("−0.10")).toBeInTheDocument();
  });
});
