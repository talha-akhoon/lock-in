import { describe, expect, it } from 'vitest'
import { makeGoal } from '../../test/factories'
import { dropIndexForY, insertIdAt, movedStepIds, orderedChildren } from './stepOrder'

describe('movedStepIds', () => {
  it('swaps a step with its neighbour', () => {
    expect(movedStepIds(['a', 'b', 'c'], 'b', 'up')).toEqual(['b', 'a', 'c'])
    expect(movedStepIds(['a', 'b', 'c'], 'b', 'down')).toEqual(['a', 'c', 'b'])
  })

  it('refuses a move past either end', () => {
    expect(movedStepIds(['a', 'b'], 'a', 'up')).toBeNull()
    expect(movedStepIds(['a', 'b'], 'b', 'down')).toBeNull()
  })
})

describe('insertIdAt', () => {
  it('moves a step to any index among the others', () => {
    expect(insertIdAt(['a', 'b', 'c'], 'a', 2)).toEqual(['b', 'c', 'a'])
    expect(insertIdAt(['a', 'b', 'c'], 'c', 0)).toEqual(['c', 'a', 'b'])
    expect(insertIdAt(['a', 'b', 'c'], 'a', 0)).toEqual(['a', 'b', 'c'])
  })
})

describe('dropIndexForY', () => {
  const rows = [
    { id: 'a', top: 0, bottom: 40 },
    { id: 'b', top: 40, bottom: 80 },
    { id: 'c', top: 80, bottom: 120 },
  ]

  it('inserts before the first row whose midpoint is below the pointer', () => {
    expect(dropIndexForY(rows, 'a', 70)).toBe(1)
    expect(dropIndexForY(rows, 'a', 110)).toBe(2)
    expect(dropIndexForY(rows, 'c', 10)).toBe(0)
  })
})

describe('orderedChildren', () => {
  it('returns children in the given id order', () => {
    const first = makeGoal({ title: 'Finish the API' })
    const second = makeGoal({ title: 'Finish the UI' })
    const parent = makeGoal({ title: 'Ship the app', children: [first, second] })

    expect(orderedChildren(parent, [second.id, first.id]).children.map((child) => child.title)).toEqual([
      'Finish the UI',
      'Finish the API',
    ])
  })
})
