import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Goal, GoalHistory, MyGoals } from '../lib/types'
import { httpError, mockFetch } from '../test/harness'
import { makeGoal } from '../test/factories'
import { keys, useReorderGoalSteps } from './queries'

afterEach(() => vi.unstubAllGlobals())

function setup() {
  const endpoints = makeGoal({ title: 'Write the endpoints' })
  const tests = makeGoal({ title: 'Write the tests' })
  const step = makeGoal({ title: 'Finish the API', children: [endpoints, tests] })
  const goal = makeGoal({ title: 'Ship the app', children: [step] })
  for (const child of [endpoints, tests]) child.parent_goal_id = step.id
  step.parent_goal_id = goal.id

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData<MyGoals>(keys.goals, { goals: [goal] } as MyGoals)
  // The goal's detail page is cached under the goal, not the step being reordered.
  client.setQueryData<GoalHistory>(keys.goalHistory(goal.id), { goal, entries: [] })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useReorderGoalSteps(), { wrapper })
  return { client, result, goal, step, endpoints, tests }
}

function subStepTitles(goal: Goal | undefined): string[] | undefined {
  return goal?.children[0]?.children.map((child) => child.title)
}

describe('useReorderGoalSteps', () => {
  it('keeps a sub-step reorder in the goals list and the parent goal’s detail page', async () => {
    const { client, result, goal, step, endpoints, tests } = setup()
    const fetchMock = mockFetch({ [`PATCH /goals/${step.id}/children/order`]: step })

    result.current.mutate({ parentId: step.id, orderedIds: [tests.id, endpoints.id] })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock.sent(`PATCH /goals/${step.id}/children/order`)[0]?.body).toEqual({
      ordered_ids: [tests.id, endpoints.id],
    })
    const reordered = ['Write the tests', 'Write the endpoints']
    expect(subStepTitles(client.getQueryData<MyGoals>(keys.goals)?.goals[0])).toEqual(reordered)
    expect(
      subStepTitles(client.getQueryData<GoalHistory>(keys.goalHistory(goal.id))?.goal),
    ).toEqual(reordered)
  })

  it('restores the old order everywhere when the save fails', async () => {
    const { client, result, goal, step, endpoints, tests } = setup()
    mockFetch({
      [`PATCH /goals/${step.id}/children/order`]: httpError(409, 'Could not reorder'),
    })

    result.current.mutate({ parentId: step.id, orderedIds: [tests.id, endpoints.id] })

    await waitFor(() => expect(result.current.isError).toBe(true))
    const original = ['Write the endpoints', 'Write the tests']
    expect(subStepTitles(client.getQueryData<MyGoals>(keys.goals)?.goals[0])).toEqual(original)
    expect(
      subStepTitles(client.getQueryData<GoalHistory>(keys.goalHistory(goal.id))?.goal),
    ).toEqual(original)
  })
})
