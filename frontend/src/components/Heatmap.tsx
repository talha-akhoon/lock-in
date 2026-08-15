import { useMemo } from 'react'
import { buildHeatmapCells, heatmapLevel } from '../lib/heatmap'
import type { Heatmap as HeatmapData } from '../lib/types'

export function Heatmap({
  data,
  title = 'Daily activity',
}: {
  data: HeatmapData
  title?: string
}) {
  const cells = useMemo(() => buildHeatmapCells(data), [data])
  return (
    <section className="card heatmap">
      <div className="section-title">
        <div>
          <span>Consistency</span>
          <h2>{title}</h2>
        </div>
        <b>
          {data.total_days_logged} {data.total_days_logged === 1 ? 'day' : 'days'} logged
        </b>
      </div>
      <div className="heatmap-grid" data-testid="heatmap-grid">
        {cells.map((cell) => (
          <span
            key={cell.date}
            data-testid="heatmap-cell"
            data-date={cell.date}
            data-level={cell.future ? 'future' : heatmapLevel(cell.count)}
            className={cell.future ? 'future' : `level-${heatmapLevel(cell.count)}`}
            title={
              cell.future
                ? cell.date
                : `${cell.date}: ${cell.count} ${cell.count === 1 ? 'update' : 'updates'}`
            }
          />
        ))}
      </div>
      <div className="heatmap-key">
        Less <i className="level-0" />
        <i className="level-1" />
        <i className="level-2" />
        <i className="level-3" />
        <i className="level-4" /> More
      </div>
    </section>
  )
}
