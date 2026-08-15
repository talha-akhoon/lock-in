import { describe, expect, it } from 'vitest'
import { makeHeatmap } from '../test/factories'
import { buildHeatmapCells, heatmapLevel } from './heatmap'

describe('heatmap cells', () => {
  it('spans the challenge window rather than a fixed length', () => {
    const short = buildHeatmapCells(makeHeatmap({ start_date: '2026-01-01', end_date: '2026-01-10' }))
    expect(short).toHaveLength(10)

    const long = buildHeatmapCells(
      makeHeatmap({ start_date: '2026-01-01', end_date: '2026-12-31', today: '2026-06-01' }),
    )
    expect(long).toHaveLength(365)
  })

  it('fills unlogged days with zero', () => {
    const cells = buildHeatmapCells(makeHeatmap())
    expect(cells.find((cell) => cell.date === '2026-01-02')).toMatchObject({ count: 0, note: null })
  })

  it('carries the update count and note for logged days', () => {
    const cells = buildHeatmapCells(makeHeatmap())
    expect(cells.find((cell) => cell.date === '2026-01-04')).toMatchObject({
      count: 2,
      note: 'Good day',
      future: false,
    })
    expect(cells.find((cell) => cell.date === '2026-01-05')?.count).toBe(7)
  })

  it('marks days after today as future', () => {
    const cells = buildHeatmapCells(makeHeatmap())
    expect(cells.find((cell) => cell.date === '2026-01-05')?.future).toBe(false)
    expect(cells.find((cell) => cell.date === '2026-01-06')?.future).toBe(true)
  })

  it('returns nothing for an impossible window', () => {
    expect(
      buildHeatmapCells(makeHeatmap({ start_date: '2026-02-01', end_date: '2026-01-01' })),
    ).toEqual([])
  })

  it('buckets intensity so one update is visibly different from none', () => {
    expect(heatmapLevel(0)).toBe(0)
    expect(heatmapLevel(1)).toBe(1)
    expect(heatmapLevel(3)).toBe(2)
    expect(heatmapLevel(5)).toBe(3)
    expect(heatmapLevel(20)).toBe(4)
  })
})
