export type ChartPath = {
  line: string;
  area: string;
  lastXpct: number;
  lastYpct: number;
};

export function buildChartPath(
  values: Array<number | null>,
  padX = 14,
  padTop = 30,
  padBot = 24,
): ChartPath {
  const width = 1000;
  const height = 300;
  const clean = values.map((value) => (value == null || Number.isNaN(value) ? null : value));
  const numeric = clean.filter((value): value is number => value != null);
  if (numeric.length === 0) {
    return { line: "", area: "", lastXpct: 0, lastYpct: 50 };
  }
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const span = max - min || 1;
  const step = clean.length <= 1 ? 0 : (width - padX * 2) / (clean.length - 1);
  const points = clean
    .map((value, index) => {
      if (value == null) {
        return null;
      }
      const x = padX + index * step;
      const y = padTop + (1 - (value - min) / span) * (height - padTop - padBot);
      return [x, y] as const;
    })
    .filter((point): point is readonly [number, number] => point != null);

  if (points.length === 0) {
    return { line: "", area: "", lastXpct: 0, lastYpct: 50 };
  }

  const line = points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const base = height - padBot;
  const area = `${line} L ${last[0]} ${base} L ${first[0]} ${base} Z`;
  return {
    line,
    area,
    lastXpct: (last[0] / width) * 100,
    lastYpct: (last[1] / height) * 100,
  };
}

export const scoreRingCircumference = 326.7;
