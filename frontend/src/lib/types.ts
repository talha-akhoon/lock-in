/** Response shapes for the LockIn API. Mirrors backend/app/api/v1/serializers.py. */

export const CATEGORIES = ['RELIGIOUS', 'PHYSICAL', 'CAREER', 'BUSINESS', 'PERSONAL'] as const
export type Category = (typeof CATEGORIES)[number]

export const TRACKING_TYPES = ['MILESTONE', 'NUMERIC', 'COUNT', 'MANUAL'] as const
export type TrackingType = (typeof TRACKING_TYPES)[number]

export type TargetDirection = 'AT_LEAST' | 'AT_MOST'
export type Visibility = 'TEAM' | 'PRIVATE'
export type Role = 'ADMIN' | 'MEMBER'
export type ChallengeStatus = 'DRAFT' | 'UPCOMING' | 'ACTIVE' | 'COMPLETED'
export type ParticipantStatus = 'ACTIVE' | 'REMOVED' | 'COMPLETED' | 'FORFEIT_DUE'

export type User = {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
}

export type AuthMe = {
  user: User
  team: { id: string; name: string } | null
  role: Role | null
  challenge_id: string | null
  challenge_status: ChallengeStatus | null
  participant_id: string | null
  goals_due_at: string | null
  goals_locked: boolean
  goals_committed_at: string | null
}

export type CurrentTeam = {
  id: string
  name: string
  role: Role
  member_count: number
}

export type TeamMember = {
  id: string
  display_name: string
  avatar_url: string | null
  email: string
  role: Role
  joined_at: string
}

export type Challenge = {
  id: string
  name: string
  description: string | null
  start_at: string
  end_at: string
  timezone: string
  status: ChallengeStatus
  goal_submission_days: number
  forfeit_amount_pence: number
  day_number: number
  total_days: number
  days_remaining: number
}

export type Goal = {
  id: string
  parent_goal_id: string | null
  category: Category
  title: string
  description: string | null
  tracking_type: TrackingType
  // Decimals arrive as strings — JSON has no exact decimal type, and rounding a
  // target the member typed would be worse than formatting one on display.
  baseline_value: string | null
  target_value: string | null
  current_value: string | null
  unit: string | null
  target_direction: TargetDirection | null
  manual_progress_percentage: number | null
  visibility: Visibility
  required: boolean
  sort_order: number
  locked_at: string | null
  completed_at: string | null
  progress_percentage: number
  private: boolean
  children: Goal[]
}

export type CategoryProgress = Partial<Record<Category, number>>

export type MyGoals = {
  goals_locked: boolean
  goals_due_at: string | null
  goals_committed_at: string | null
  overall_progress: number
  categories: CategoryProgress
  goals: Goal[]
}

export type MemberCard = {
  user_id: string
  display_name: string
  avatar_url: string | null
  is_self: boolean
  overall_progress: number
  categories: CategoryProgress
  streak: number
  goals_locked: boolean
  goals_submitted: boolean
  goals_committed: number
  goals_completed: number
  participant_status: ParticipantStatus
}

export type Dashboard = {
  challenge: Challenge
  team_progress: number
  members: MemberCard[]
}

export type HeatmapDay = {
  date: string
  note: string | null
  updates: number
}

export type Heatmap = {
  start_date: string
  end_date: string
  today: string
  pre_start: boolean
  streak: number
  total_days_logged: number
  days: HeatmapDay[]
}

export type MemberProfile = {
  user: TeamMember
  is_self: boolean
  challenge_id: string
  participant_status: ParticipantStatus
  goals_locked: boolean
  goals_due_at: string
  goals_committed_at: string | null
  overall_progress: number
  categories: CategoryProgress
  goals_committed: number
  goals_completed: number
  private_committed: number
  private_completed: number
  goals: Goal[]
  streak: number
  heatmap: Heatmap
}

export type ActivityEntry = {
  id: string
  user_id: string
  display_name: string
  avatar_url: string | null
  goal_id: string
  goal_title: string
  goal_category: Category
  unit: string | null
  entry_date: string
  numeric_value: string | null
  numeric_delta: string | null
  manual_percentage: number | null
  completed: boolean | null
  note: string | null
  created_at: string
}

export type NotificationType =
  | 'GOALS_DUE_SOON'
  | 'GOALS_LOCK_TOMORROW'
  | 'GOALS_LOCKED'
  | 'CHALLENGE_MILESTONE'
  | 'CHALLENGE_COMPLETE'
  | 'MEMBER_COMPLETED_GOAL'
  | 'MEMBER_JOINED'

export type Notification = {
  id: string
  type: NotificationType
  title: string
  body: string | null
  link_path: string | null
  read_at: string | null
  created_at: string
}

export type NotificationFeed = {
  unread_count: number
  notifications: Notification[]
}

export type Invitation = {
  id: string
  code_prefix: string
  expires_at: string | null
  max_uses: number | null
  use_count: number
  revoked_at: string | null
  created_at: string
  /** Present only in the create response; the plaintext code is never stored. */
  code?: string
}

export type ProgressEntry = {
  id: string
  entry_date: string
  numeric_value: string | null
  numeric_delta: string | null
  manual_percentage: number | null
  completed: boolean | null
  note: string | null
  evidence_url: string | null
  created_at: string
}

export type GoalHistory = {
  goal: Goal
  entries: ProgressEntry[]
}

export type DayCheckin = {
  date: string
  note: string | null
  exists: boolean
  pre_start: boolean
  goals: Goal[]
}

export type Outcome = {
  participant_id: string
  user_id: string
  display_name: string
  avatar_url: string | null
  required_goals_total: number
  required_goals_completed: number
  optional_goals_total: number
  optional_goals_completed: number
  final_progress_percentage: number
  succeeded: boolean
  total_forfeit_pence: number
}

export type ForfeitLine = {
  id: string
  from_user_id: string
  from_display_name: string
  to_user_id: string
  to_display_name: string
  amount_pence: number
  status: 'OUTSTANDING' | 'SETTLED'
  settled_at: string | null
}

export type Outcomes = {
  challenge: Challenge
  outcomes: Outcome[]
  forfeits: ForfeitLine[]
}

export type AuditLog = {
  id: string
  actor_user_id: string
  actor: string
  action: string
  entity_type: string
  entity_id: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export type ParticipantRow = {
  participant_id: string
  challenge_id: string
  challenge_name: string
  user_id: string
  display_name: string
  status: ParticipantStatus
  goals_due_at: string
  goals_locked_at: string | null
  goals_committed_at: string | null
  goals_committed: number
  first_goal_id: string | null
}

export type GoalInput = {
  category: Category
  title: string
  description: string | null
  tracking_type: TrackingType
  baseline_value: number | null
  target_value: number | null
  current_value: number | null
  unit: string | null
  target_direction: TargetDirection | null
  manual_progress_percentage: number | null
  visibility: Visibility
  required: boolean
  parent_goal_id?: string | null
}

export type CheckinUpdate = {
  goal_id: string
  numeric_value?: number
  numeric_delta?: number
  manual_percentage?: number
  completed?: boolean
  note?: string | null
}

export type CheckinPayload = {
  date: string
  note: string | null
  updates: CheckinUpdate[]
}
