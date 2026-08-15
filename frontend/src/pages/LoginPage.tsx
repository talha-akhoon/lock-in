import { GoogleLogin } from '@react-oauth/google'
import { CalendarCheck, LockKeyhole, Target, Users } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth, useGoogleSignIn } from '../hooks/queries'
import { Loading } from '../components/primitives'

export function LoginPage() {
  const auth = useAuth()
  const signIn = useGoogleSignIn()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const configured = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID)

  if (auth.isLoading) return <Loading label="Checking your session" />
  if (auth.data) return <Navigate to="/dashboard" replace />

  return (
    <main className="login-page">
      <section className="login-copy">
        <div className="brand">
          <span>LI</span> LockIn
        </div>
        <div className="eyebrow">Six months. No excuses.</div>
        <h1>
          You said you would.
          <br />
          <em>Now prove it.</em>
        </h1>
        <p>Commit publicly. Track consistently. Finish what you said you would finish.</p>
        <div className="principles">
          <div>
            <Target />
            <span>
              <b>Commit</b> to meaningful goals
            </span>
          </div>
          <div>
            <CalendarCheck />
            <span>
              <b>Check in</b> and show your work
            </span>
          </div>
          <div>
            <Users />
            <span>
              <b>Stay accountable</b> to your team
            </span>
          </div>
        </div>
      </section>
      <section className="login-card">
        <div className="contract-mark">
          <LockKeyhole />
        </div>
        <h2>Enter the lock-in</h2>
        <p>Your team is waiting.</p>
        {configured ? (
          <GoogleLogin
            width="320"
            onError={() => setError('Google could not verify you. Try again.')}
            onSuccess={async ({ credential }) => {
              if (!credential) {
                setError('Google did not return a credential.')
                return
              }
              try {
                await signIn.mutateAsync(credential)
                navigate('/dashboard')
              } catch (reason) {
                setError((reason as Error).message)
              }
            }}
          />
        ) : (
          <div className="setup-note">
            Add <code>VITE_GOOGLE_CLIENT_ID</code> to enable sign-in.
          </div>
        )}
        {error && <p className="error">{error}</p>}
        <small>By continuing, you accept the commitment you make to your team.</small>
      </section>
    </main>
  )
}
