import { cx } from '../cx'
import styles from './LineChart.module.css'

export interface LineChartSeries {
  label: string
  /** Values align with `labels` by index; missing entries count as 0. */
  values: number[]
}

export interface LineChartProps {
  /** One x-axis label per point. */
  labels: string[]
  /** The plotted series. Identity is carried by line style and the legend, never colour alone. */
  series: LineChartSeries[]
  /** Accessible name for the chart; also captions the table equivalent. */
  title: string
  className?: string
}

const lineStyles = [styles.seriesA, styles.seriesB, styles.seriesC]

/**
 * Count-based line chart with a mandatory table equivalent in the DOM
 * (visually hidden, per D2 section 8.4's data-table rule). The SVG is
 * decorative; the table carries the accessible data.
 */
export function LineChart({ labels, series, title, className }: LineChartProps) {
  const maximum = Math.max(1, ...series.flatMap((line) => line.values))
  const x = (index: number) => (labels.length <= 1 ? 50 : (index / (labels.length - 1)) * 100)
  const y = (value: number) => 94 - (value / maximum) * 88
  const points = (line: LineChartSeries) =>
    labels.map((_, index) => `${x(index)},${y(line.values[index] ?? 0)}`).join(' ')

  return (
    <figure className={cx(styles.chart, className)} aria-label={title}>
      <figcaption className={styles.legend}>
        {series.map((line, index) => (
          <span key={line.label} className={styles.legendItem}>
            <svg className={styles.swatch} viewBox="0 0 20 8" aria-hidden="true">
              <line
                x1="1"
                y1="4"
                x2="19"
                y2="4"
                className={cx(styles.line, lineStyles[index % lineStyles.length])}
              />
            </svg>
            {line.label}
          </span>
        ))}
      </figcaption>
      <svg
        className={styles.plot}
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        {[6, 28, 50, 72, 94].map((gridline) => (
          <line
            key={gridline}
            x1="0"
            y1={gridline}
            x2="100"
            y2={gridline}
            className={styles.gridline}
          />
        ))}
        {series.map((line, index) => (
          <polyline
            key={line.label}
            points={points(line)}
            vectorEffect="non-scaling-stroke"
            className={cx(styles.line, lineStyles[index % lineStyles.length])}
          />
        ))}
      </svg>
      <div
        className={cx(styles.axis, labels.length === 1 && styles.axisSingle)}
        aria-hidden="true"
      >
        {labels.map((label, index) => (
          <span key={`${label}-${index}`}>{label}</span>
        ))}
      </div>
      <table className={styles.table}>
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Period</th>
            {series.map((line) => (
              <th key={line.label} scope="col">
                {line.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, index) => (
            <tr key={`${label}-${index}`}>
              <th scope="row">{label}</th>
              {series.map((line) => (
                <td key={line.label}>{line.values[index] ?? 0}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
