import type { Category, TrackingType } from './types'

export const TRACKING_HELP: Record<
  TrackingType,
  { title: string; body: string; checkin: string; avoid: string; example: string }
> = {
  MILESTONE: {
    title: 'Done or not done',
    body: 'A single tick. It stays unfinished until the day you mark it complete.',
    checkin: 'Check-in is a tick when it is finished.',
    avoid: 'Not for anything you will measure with a number.',
    example: 'Get promoted, finish the book, deploy the app.',
  },
  NUMERIC: {
    title: 'Update the current figure',
    body: 'Set where you are now when you add the goal. After that, record the current figure when it changes. Progress is how close that number is to the target, up or down.',
    checkin: 'Check-in asks what the number is now — not what you did today.',
    avoid: 'Not for sessions, pages, or kilometres you add up over the challenge.',
    example: 'Deadlift 180kg, body fat to 12%, £2k monthly revenue.',
  },
  COUNT: {
    title: "Add today's amount",
    body: 'Set how many you already have when you add the goal. After that, check-in asks for today’s amount, not a new overall figure. What you already have counts toward the target.',
    checkin: 'Check-in asks how much you did today. Those amounts add up.',
    avoid: 'Not for a lift, a weight, or a time you re-measure.',
    example: '150 pages of reading, 12 books, 100 gym sessions.',
  },
  MANUAL: {
    title: 'Set a percentage yourself',
    body: 'There is no automatic measure. Set where you are now (0–100) when you add the goal, then update it when you think you have moved.',
    checkin: 'Check-in asks for a new 0–100 figure.',
    avoid: 'Not when you already have a number or a daily count.',
    example: 'A side project or habit you can feel but not count cleanly.',
  },
}

export const TRACKING_EXAMPLES: Record<Category, Partial<Record<TrackingType, string>>> = {
  RELIGIOUS: {
    NUMERIC: 'Memorised pages, minutes of prayer.',
    COUNT: '150 pages of reading, 30 days of prayer.',
    MILESTONE: 'Finish a book of scripture.',
  },
  PHYSICAL: {
    NUMERIC: 'Deadlift 120kg, bodyweight 75kg, 5k in 22 minutes.',
    COUNT: '100 gym sessions, 500km run, 10,000 push-ups.',
    MILESTONE: 'Run a half marathon.',
  },
  CAREER: {
    NUMERIC: 'Salary band, interview count this month.',
    COUNT: '50 applications, 12 published posts.',
    MILESTONE: 'Get promoted, land the role.',
  },
  BUSINESS: {
    NUMERIC: '£2k monthly revenue, 20 paying customers.',
    COUNT: '100 sales calls, 12 shipped releases.',
    MILESTONE: 'Launch the product.',
  },
  PERSONAL: {
    NUMERIC: 'Savings balance, hours of sleep.',
    COUNT: '52 date nights, 24 books.',
    MILESTONE: 'Pay off the credit card.',
  },
}

export function trackingExample(type: TrackingType, category?: Category): string {
  return (category && TRACKING_EXAMPLES[category][type]) || TRACKING_HELP[type].example
}

export const TRACKING_HELP_INTRO =
  'The difference is what check-in will ask. A lift or a weight is the current figure. Sessions or kilometres are today’s amount.'

export const STEP_HELP_TITLE = 'What is a step?'

export const STEP_HELP_BODY =
  'A step is a named piece of this goal. You check in on the steps, not the parent. The parent’s progress is the average of its required steps. The first step replaces the parent’s own figure with that average, and once locked you cannot remove it — so add steps before you commit. Use the arrows next to a step to change the order; check-in follows it, and that still works after the lock.'

export const STEP_HELP_WHEN =
  'Use it when the work splits into a few finish-lines — “Ship the app” with “Finish the API” and “Finish the UI”. Skip it for a running total you already measure, like 150 pages of reading — turning that into steps throws the figure away, and once locked that is refused.'
