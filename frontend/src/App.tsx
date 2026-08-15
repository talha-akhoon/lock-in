import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './layouts/AppShell'
import { RequireAdmin, RequireAuth, RequireTeam } from './layouts/guards'
import { ActivityPage } from './pages/ActivityPage'
import { CheckInPage } from './pages/CheckInPage'
import { DashboardPage } from './pages/DashboardPage'
import { GoalDetailPage } from './pages/GoalDetailPage'
import { GoalsPage } from './pages/GoalsPage'
import { LoginPage } from './pages/LoginPage'
import { MemberProfilePage } from './pages/MemberProfilePage'
import { ResultsPage } from './pages/ResultsPage'
import { SettingsPage } from './pages/SettingsPage'
import { TeamPage } from './pages/TeamPage'
import { AdminAuditPage } from './pages/admin/AdminAuditPage'
import { AdminChallengePage } from './pages/admin/AdminChallengePage'
import { AdminInvitationsPage } from './pages/admin/AdminInvitationsPage'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminMembersPage } from './pages/admin/AdminMembersPage'
import { AdminTeamPage } from './pages/admin/AdminTeamPage'
import { CreateChallengePage } from './pages/onboarding/CreateChallengePage'
import { GoalWizardPage } from './pages/onboarding/GoalWizardPage'
import { StartPage } from './pages/onboarding/StartPage'
import { WelcomePage } from './pages/onboarding/WelcomePage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Onboarding is inside RequireAuth: redeeming an invite needs a session. */}
      <Route element={<RequireAuth />}>
        <Route path="/onboarding/invitation" element={<Navigate to="/onboarding/start" replace />} />
        <Route path="/onboarding/start" element={<StartPage />} />
        <Route element={<RequireTeam />}>
          <Route path="/onboarding/challenge" element={<CreateChallengePage />} />
          <Route path="/onboarding/welcome" element={<WelcomePage />} />
          <Route path="/onboarding/goals" element={<GoalWizardPage />} />

          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/check-in" element={<CheckInPage />} />
            <Route path="/goals" element={<GoalsPage />} />
            <Route path="/goals/:goalId" element={<GoalDetailPage />} />
            <Route path="/team" element={<TeamPage />} />
            <Route path="/team/members/:userId" element={<MemberProfilePage />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route element={<RequireAdmin />}>
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<Navigate to="/admin/team" replace />} />
                <Route path="team" element={<AdminTeamPage />} />
                <Route path="challenge" element={<AdminChallengePage />} />
                <Route path="invitations" element={<AdminInvitationsPage />} />
                <Route path="members" element={<AdminMembersPage />} />
                <Route path="audit" element={<AdminAuditPage />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
