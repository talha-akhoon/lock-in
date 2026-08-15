import type { TrackingType } from './types'

export const TRACKING_HELP: Record<
  TrackingType,
  { title: string; body: string; example: string }
> = {
  MILESTONE: {
    title: 'Done or not done',
    body: 'A single tick. It stays unfinished until the day you mark it complete.',
    example: 'Get promoted, finish the book, deploy the app.',
  },
  NUMERIC: {
    title: 'A number moving to a target',
    body: 'Set where you are now when you add the goal. After that, record the current figure when it changes. Progress is how close that number is to the target, up or down.',
    example: 'Deadlift 180kg, body fat to 12%, £2k monthly revenue.',
  },
  COUNT: {
    title: 'A running total',
    body: 'Set how many you already have when you add the goal. After that, check-in asks for today’s amount, not a new overall figure.',
    example: '150 pages of reading, 12 books, 100 gym sessions.',
  },
  MANUAL: {
    title: 'A percentage you set yourself',
    body: 'There is no automatic measure. Set where you are now (0–100) when you add the goal, then update it when you think you have moved.',
    example: 'A side project or habit you can feel but not count cleanly.',
  },
}

export const TRACKING_HELP_INTRO =
  'Pick the option that matches how you will know you are done, not how important the goal feels.'

export const STEP_HELP_TITLE = 'What is a step?'

export const STEP_HELP_BODY =
  'A step is a named piece of this goal. You check in on the steps, not the parent. The parent’s progress is the average of its required steps.'

export const STEP_HELP_WHEN =
  'Use it when the work splits into a few finish-lines — “Ship the app” with “Finish the API” and “Finish the UI”. Skip it for a running total you already measure, like 150 pages of reading.'
