import { describe, expect, it } from 'vitest'
import { makeGoal } from '../../test/factories'
import { movedStepIds, orderedChildren } from './stepOrder'

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
