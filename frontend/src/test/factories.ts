import type {
  AuthMe,
  Challenge,
  Dashboard,
  Goal,
  Heatmap,
  MemberCard,
  MemberProfile,
  MyGoals,
  TeamMember,
} from '../lib/types'

export const USER_ID = '11111111-1111-1111-1111-111111111111'
export const OTHER_ID = '22222222-2222-2222-2222-222222222222'
export const TEAM_ID = '33333333-3333-3333-3333-333333333333'
export const CHALLENGE_ID = '44444444-4444-4444-4444-444444444444'

export function makeAuth(overrides: Partial<AuthMe> = {}): AuthMe {
  return {
    user: {
      id: USER_ID,
      email: 'sam@example.com',
      display_name: 'Sam Ali',
      avatar_url: null,
    },
    team: { id: TEAM_ID, name: 'The Sunday Circle' },
    role: 'MEMBER',
    challenge_id: CHALLENGE_ID,
    challenge_status: 'ACTIVE',
    participant_id: '55555555-5555-5555-5555-555555555555',
    goals_due_at: '2026-01-06T00:00:00Z',
    goals_locked: false,
    goals_committed_at: null,
    ...overrides,
  }
}

export function makeChallenge(overrides: Partial<Challenge> = {}): Challenge {
  return {
    id: CHALLENGE_ID,
    name: 'Six-Month Lock-In',
    description: null,
    start_at: '2026-01-01T00:00:00Z',
    end_at: '2026-07-01T00:00:00Z',
    timezone: 'Europe/London',
    status: 'ACTIVE',
    goal_submission_days: 5,
    forfeit_amount_pence: 25000,
    day_number: 10,
    total_days: 182,
    days_remaining: 172,
    ...overrides,
  }
}

let goalCounter = 0

/** The API serialises decimals to strings with four places; mirror that. */
function decimal(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined) return null
  return typeof value === 'number' ? value.toFixed(4) : value
}

type GoalOverrides = Partial<Omit<Goal, 'baseline_value' | 'target_value' | 'current_value'>> & {
  baseline_value?: string | number | null
  target_value?: string | number | null
  current_value?: string | number | null
}

export function makeGoal(overrides: GoalOverrides = {}): Goal {
  goalCounter += 1
  const { baseline_value, target_value, current_value, ...rest } = overrides
  return {
    id: `goal-${goalCounter}`,
    parent_goal_id: null,
    category: 'PHYSICAL',
    title: `Goal ${goalCounter}`,
    description: null,
    tracking_type: 'MILESTONE',
    baseline_value: decimal(baseline_value),
    target_value: decimal(target_value),
    current_value: decimal(current_value),
    unit: null,
    target_direction: null,
    manual_progress_percentage: null,
    visibility: 'TEAM',
    required: true,
    sort_order: 0,
    locked_at: null,
    completed_at: null,
    progress_percentage: 0,
    private: false,
    children: [],
    ...rest,
  }
}

export function makeMyGoals(goals: Goal[], overrides: Partial<MyGoals> = {}): MyGoals {
  return {
    goals_locked: false,
    goals_due_at: '2026-01-06T00:00:00Z',
    goals_committed_at: null,
    overall_progress: 0,
    categories: {},
    goals,
    ...overrides,
  }
}

export function makeMemberCard(overrides: Partial<MemberCard> = {}): MemberCard {
  return {
    user_id: OTHER_ID,
    display_name: 'Yusuf Khan',
    avatar_url: null,
    is_self: false,
    overall_progress: 42,
    categories: { PHYSICAL: 42 },
    streak: 3,
    goals_locked: true,
    goals_submitted: true,
    goals_committed: 4,
    goals_completed: 1,
    participant_status: 'ACTIVE',
    ...overrides,
  }
}

export function makeDashboard(members: MemberCard[], teamProgress = 42): Dashboard {
  return { challenge: makeChallenge(), team_progress: teamProgress, members }
}

export function makeHeatmap(overrides: Partial<Heatmap> = {}): Heatmap {
  return {
    start_date: '2026-01-01',
    end_date: '2026-01-10',
    today: '2026-01-05',
    pre_start: false,
    streak: 2,
    total_days_logged: 2,
    days: [
      { date: '2026-01-04', note: 'Good day', updates: 2 },
      { date: '2026-01-05', note: null, updates: 7 },
    ],
    ...overrides,
  }
}

export function makeTeamMember(overrides: Partial<TeamMember> = {}): TeamMember {
  return {
    id: OTHER_ID,
    display_name: 'Yusuf Khan',
    avatar_url: null,
    email: 'yusuf@example.com',
    role: 'MEMBER',
    joined_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeMemberProfile(overrides: Partial<MemberProfile> = {}): MemberProfile {
  return {
    user: makeTeamMember(),
    is_self: false,
    challenge_id: CHALLENGE_ID,
    participant_status: 'ACTIVE',
    goals_locked: true,
    goals_due_at: '2026-01-06T00:00:00Z',
    goals_committed_at: '2026-01-03T00:00:00Z',
    overall_progress: 50,
    categories: { PHYSICAL: 50 },
    goals_committed: 2,
    goals_completed: 1,
    private_committed: 0,
    private_completed: 0,
    goals: [],
    streak: 3,
    heatmap: makeHeatmap(),
    ...overrides,
  }
}
