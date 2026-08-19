/** Typed query and mutation hooks, one per resource. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'
import { api, del, patch, post } from '../lib/api'
import type {
  ActivityEntry,
  AuditLog,
  AuthMe,
  Challenge,
  CurrentTeam,
  Dashboard,
  DayCheckin,
  Goal,
  GoalHistory,
  GoalInput,
  Heatmap,
  Invitation,
  MemberProfile,
  MyGoals,
  NotificationFeed,
  Outcomes,
  ParticipantRow,
  Role,
  TeamMember,
  CheckinPayload,
  McpToken,
  PushConfig,
} from '../lib/types'

export const keys = {
  auth: ['auth'] as const,
  team: ['team'] as const,
  members: ['members'] as const,
  member: (userId: string) => ['member', userId] as const,
  challenge: ['challenge'] as const,
  dashboard: (challengeId?: string) => ['dashboard', challengeId] as const,
  activity: (challengeId?: string) => ['activity', challengeId] as const,
  outcomes: (challengeId?: string) => ['outcomes', challengeId] as const,
  goals: ['goals'] as const,
  goal: (goalId: string) => ['goal', goalId] as const,
  goalHistory: (goalId: string) => ['goal-history', goalId] as const,
  checkins: ['checkins'] as const,
  checkinDay: (day: string) => ['checkin', day] as const,
  notifications: ['notifications'] as const,
  invitations: ['invitations'] as const,
  audit: ['audit'] as const,
  participants: ['participants'] as const,
  mcpTokens: ['mcp-tokens'] as const,
  pushConfig: ['push-config'] as const,
}

export function useAuth(): UseQueryResult<AuthMe> {
  return useQuery({
    queryKey: keys.auth,
    queryFn: () => api<AuthMe>('/auth/me'),
    retry: false,
    staleTime: 15_000,
  })
}

export function useCurrentTeam(enabled = true) {
  return useQuery({
    queryKey: keys.team,
    queryFn: () => api<CurrentTeam>('/teams/current'),
    enabled,
  })
}

export function useTeamMembers(teamId: string | null | undefined) {
  return useQuery({
    queryKey: keys.members,
    queryFn: () => api<TeamMember[]>(`/teams/${teamId}/members`),
    enabled: Boolean(teamId),
  })
}

export function useMemberProfile(
  teamId: string | null | undefined,
  userId: string | undefined,
) {
  return useQuery({
    queryKey: keys.member(userId ?? 'none'),
    queryFn: () => api<MemberProfile>(`/teams/${teamId}/members/${userId}`),
    enabled: Boolean(teamId && userId),
    retry: false,
  })
}

export function useChallenge() {
  return useQuery({
    queryKey: keys.challenge,
    queryFn: () => api<Challenge>('/challenges/current'),
    retry: false,
  })
}

export function useDashboard(challengeId: string | null | undefined) {
  return useQuery({
    queryKey: keys.dashboard(challengeId ?? undefined),
    queryFn: () => api<Dashboard>(`/challenges/${challengeId}/dashboard`),
    enabled: Boolean(challengeId),
  })
}

export function useActivity(challengeId: string | null | undefined) {
  return useQuery({
    queryKey: keys.activity(challengeId ?? undefined),
    queryFn: () => api<ActivityEntry[]>(`/challenges/${challengeId}/activity`),
    enabled: Boolean(challengeId),
  })
}

export function useOutcomes(challengeId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: keys.outcomes(challengeId ?? undefined),
    queryFn: () => api<Outcomes>(`/challenges/${challengeId}/outcomes`),
    enabled: Boolean(challengeId) && enabled,
    retry: false,
  })
}

export function useMyGoals() {
  return useQuery({
    queryKey: keys.goals,
    queryFn: () => api<MyGoals>('/me/goals'),
    retry: false,
  })
}

export function useGoal(goalId: string | undefined) {
  return useQuery({
    queryKey: keys.goal(goalId ?? 'none'),
    queryFn: () => api<Goal>(`/goals/${goalId}`),
    enabled: Boolean(goalId),
    retry: false,
  })
}

export function useGoalHistory(goalId: string | undefined) {
  return useQuery({
    queryKey: keys.goalHistory(goalId ?? 'none'),
    queryFn: () => api<GoalHistory>(`/goals/${goalId}/progress`),
    enabled: Boolean(goalId),
    retry: false,
  })
}

export function useHeatmap() {
  return useQuery({
    queryKey: keys.checkins,
    queryFn: () => api<Heatmap>('/me/checkins'),
    retry: false,
  })
}

export function useDayCheckin(day: string) {
  return useQuery({
    queryKey: keys.checkinDay(day),
    queryFn: () => api<DayCheckin>(`/me/checkins/${day}`),
    retry: false,
  })
}

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: keys.notifications,
    queryFn: () => api<NotificationFeed>('/me/notifications'),
    enabled,
    refetchInterval: 120_000,
  })
}

export function useInvitations(teamId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: keys.invitations,
    queryFn: () => api<Invitation[]>(`/teams/${teamId}/invitations`),
    enabled: Boolean(teamId) && enabled,
  })
}

export function useAuditLogs(teamId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: keys.audit,
    queryFn: () => api<AuditLog[]>(`/teams/${teamId}/audit-logs`),
    enabled: Boolean(teamId) && enabled,
  })
}

export function useParticipants(teamId: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: keys.participants,
    queryFn: () => api<ParticipantRow[]>(`/teams/${teamId}/participants`),
    enabled: Boolean(teamId) && enabled,
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/** Anything that changes goals also changes progress everywhere it is shown. */
function useGoalInvalidation() {
  const client = useQueryClient()
  return () => {
    client.invalidateQueries({ queryKey: keys.goals })
    client.invalidateQueries({ queryKey: keys.auth })
    client.invalidateQueries({ queryKey: ['dashboard'] })
    client.invalidateQueries({ queryKey: ['activity'] })
    client.invalidateQueries({ queryKey: ['member'] })
    client.invalidateQueries({ queryKey: keys.checkins })
  }
}

export function useCreateGoal() {
  const invalidate = useGoalInvalidation()
  return useMutation({
    mutationFn: (input: GoalInput) => post<Goal>('/me/goals', input),
    onSuccess: invalidate,
  })
}

export function useUpdateGoal(goalId: string) {
  const invalidate = useGoalInvalidation()
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: Partial<GoalInput>) => patch<Goal>(`/goals/${goalId}`, input),
    onSuccess: () => {
      invalidate()
      client.invalidateQueries({ queryKey: keys.goal(goalId) })
    },
  })
}

export function useDeleteGoal() {
  const invalidate = useGoalInvalidation()
  return useMutation({
    mutationFn: (goalId: string) => del(`/goals/${goalId}`),
    onSuccess: invalidate,
  })
}

export function useCommitGoals() {
  const invalidate = useGoalInvalidation()
  return useMutation({
    mutationFn: () => post<{ locked: boolean; locked_at: string }>('/me/goals/commit'),
    onSuccess: invalidate,
  })
}

export function useSaveCheckin() {
  const invalidate = useGoalInvalidation()
  return useMutation({
    mutationFn: (payload: CheckinPayload) => post('/me/checkins', payload),
    onSuccess: invalidate,
  })
}

export function useCreateTeam() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => post<{ id: string; name: string }>('/teams', { name }),
    onSuccess: () => client.invalidateQueries(),
  })
}

export type ChallengeInput = {
  name: string
  description: string | null
  start_at: string
  end_at: string
  goal_submission_days: number
  forfeit_amount_pence: number
}

export function useCreateChallenge(teamId: string | null | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: ChallengeInput) =>
      post<Challenge>(`/teams/${teamId}/challenges`, input),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useUpdateChallenge(challengeId: string | null | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: Partial<ChallengeInput> & { publish?: boolean }) =>
      patch<Challenge>(`/challenges/${challengeId}`, input),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useRedeemInvitation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (code: string) =>
      post<{ team_id: string }>('/invitations/redeem', { code: code.toUpperCase() }),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useCreateInvitation(teamId: string | null | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { max_uses: number | null; expires_at: string | null }) =>
      post<Invitation>(`/teams/${teamId}/invitations`, input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.invitations })
      client.invalidateQueries({ queryKey: keys.audit })
    },
  })
}

export function useRevokeInvitation(teamId: string | null | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (invitationId: string) =>
      del(`/teams/${teamId}/invitations/${invitationId}`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.invitations })
      client.invalidateQueries({ queryKey: keys.audit })
    },
  })
}

export function useRemoveMember(teamId: string | null | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => del(`/teams/${teamId}/members/${userId}`),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useChangeRole(teamId: string | null | undefined) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      patch<TeamMember>(`/teams/${teamId}/members/${userId}`, { role }),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useUnlockCommitment() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (goalId: string) =>
      post<{ unlocked_until: string }>(`/goals/${goalId}/unlock`),
    onSuccess: () => client.invalidateQueries(),
  })
}

export function useMarkNotificationRead() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (notificationId: string) =>
      post(`/me/notifications/${notificationId}/read`),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.notifications }),
  })
}

export function useMarkAllNotificationsRead() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => post('/me/notifications/read-all'),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.notifications }),
  })
}

export function useMcpTokens() {
  return useQuery({
    queryKey: keys.mcpTokens,
    queryFn: () => api<McpToken[]>('/me/mcp-tokens'),
  })
}

export function usePushConfig() {
  return useQuery({
    queryKey: keys.pushConfig,
    queryFn: () => api<PushConfig>('/me/push/config'),
  })
}

export function useCreateMcpToken() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => post<McpToken>('/me/mcp-tokens', { name }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.mcpTokens }),
  })
}

export function useRevokeMcpToken() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (tokenId: string) => del(`/me/mcp-tokens/${tokenId}`),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.mcpTokens }),
  })
}

export function useLogout() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => post('/auth/logout'),
    onSuccess: () => client.clear(),
  })
}

export function useGoogleSignIn() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (idToken: string) => post('/auth/google', { id_token: idToken }),
    onSuccess: () => client.invalidateQueries(),
  })
}
