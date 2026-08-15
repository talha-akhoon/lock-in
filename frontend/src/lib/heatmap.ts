import type { Heatmap } from './types'

export type HeatmapCell = {
  date: string
  count: number
  note: string | null
  future: boolean
}

const DAY_MS = 86_400_000

/**
 * Expands the challenge window into one cell per day, marking logged days.
 * The length comes from the challenge itself, so a 90-day and a 365-day
 * challenge both render correctly.
 */
export function buildHeatmapCells(data: Heatmap): HeatmapCell[] {
  const logged = new Map(data.days.map((day) => [day.date, day]))
  const start = Date.parse(`${data.start_date}T00:00:00Z`)
  const end = Date.parse(`${data.end_date}T00:00:00Z`)
  const today = Date.parse(`${data.today}T00:00:00Z`)
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return []

  const cells: HeatmapCell[] = []
  for (let time = start; time <= end; time += DAY_MS) {
    const date = new Date(time).toISOString().slice(0, 10)
    const entry = logged.get(date)
    cells.push({
      date,
      count: entry?.updates ?? 0,
      note: entry?.note ?? null,
      future: time > today,
    })
  }
  return cells
}

export function heatmapLevel(count: number): number {
  if (count <= 0) return 0
  if (count === 1) return 1
  if (count <= 3) return 2
  if (count <= 5) return 3
  return 4
}
