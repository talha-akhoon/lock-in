import { ArrowDownRight, ArrowUpRight, Check, Trophy, TriangleAlert } from 'lucide-react'
import { Avatar, Empty, ErrorState, Loading, PageHeader, Pill, Progress } from '../components/primitives'
import { useChallenge, useOutcomes } from '../hooks/queries'
import { formatDate, formatPence } from '../lib/format'
import type { ForfeitLine } from '../lib/types'
import { useAuthContext } from '../layouts/authContext'

export function ResultsPage() {
  const auth = useAuthContext()
  const challenge = useChallenge()
  const outcomes = useOutcomes(auth.challenge_id)

  if (challenge.isLoading || outcomes.isLoading) return <Loading label="Working out the results" />

  if (outcomes.isError) {
    const status = (outcomes.error as { status?: number }).status
    if (status === 409) {
      return (
        <>
          <PageHeader eyebrow="The reckoning" title="Results" />
          <Empty
            title="Not finished yet"
            body={
              challenge.data
                ? `Results unlock when the challenge ends on ${formatDate(challenge.data.end_at)}. ${challenge.data.days_remaining} days to go.`
                : 'Results unlock when the challenge ends.'
            }
          />
        </>
      )
    }
    return <ErrorState body={(outcomes.error as Error).message} />
  }

  const data = outcomes.data!
  const mine = data.outcomes.find((outcome) => outcome.user_id === auth.user.id)
  const owed = data.forfeits.filter((line) => line.to_user_id === auth.user.id)
  const owing = data.forfeits.filter((line) => line.from_user_id === auth.user.id)
  const owedTotal = owed.reduce((sum, line) => sum + line.amount_pence, 0)
  const owingTotal = owing.reduce((sum, line) => sum + line.amount_pence, 0)

  return (
    <>
      <PageHeader
        eyebrow="The reckoning"
        title={data.challenge.name}
        description={`Ran ${formatDate(data.challenge.start_at)} to ${formatDate(data.challenge.end_at)}.`}
      />

      {mine &&
        (mine.succeeded ? (
          <section className="verdict card success">
            <Trophy />
            <div>
              <span className="eyebrow">Your result</span>
              <h2>You did what you said you would.</h2>
              <p>
                {mine.required_goals_completed} of {mine.required_goals_total} required goals
                complete, finishing at {mine.final_progress_percentage}%.
                {owedTotal > 0
                  ? ` You are owed ${formatPence(owedTotal)}.`
                  : ' Nobody owes you anything — everyone else finished too.'}
              </p>
            </div>
          </section>
        ) : (
          <section className="verdict card failure">
            <TriangleAlert />
            <div>
              <span className="eyebrow">Your result</span>
              <h2>You fell short.</h2>
              <p>
                {mine.required_goals_total === 0
                  ? 'You never committed any goals.'
                  : `${mine.required_goals_completed} of ${mine.required_goals_total} required goals complete, finishing at ${mine.final_progress_percentage}%.`}{' '}
                You owe {formatPence(owingTotal)} in total.
              </p>
            </div>
          </section>
        ))}

      {(owing.length > 0 || owed.length > 0) && (
        <section className="card">
          <div className="section-title">
            <div>
              <span>Settlement</span>
              <h2>What changes hands</h2>
            </div>
          </div>
          {owing.length > 0 && (
            <>
              <h3 className="settle-head">
                <ArrowUpRight /> You pay {formatPence(owingTotal)}
              </h3>
              {owing.map((line) => (
                <ForfeitRow key={line.id} line={line} counterparty={line.to_display_name} />
              ))}
            </>
          )}
          {owed.length > 0 && (
            <>
              <h3 className="settle-head">
                <ArrowDownRight /> You receive {formatPence(owedTotal)}
              </h3>
              {owed.map((line) => (
                <ForfeitRow key={line.id} line={line} counterparty={line.from_display_name} />
              ))}
            </>
          )}
        </section>
      )}

      <div className="section-heading">
        <div>
          <span className="eyebrow">Final standings</span>
          <h2>Everyone's result</h2>
        </div>
      </div>
      <section className="people-list card">
        {data.outcomes.map((outcome) => (
          <div className="outcome-row" key={outcome.participant_id}>
            <Avatar name={outcome.display_name} url={outcome.avatar_url} />
            <div>
              <b>{outcome.display_name}</b>
              <span>
                {outcome.required_goals_completed}/{outcome.required_goals_total} required ·{' '}
                {outcome.optional_goals_completed}/{outcome.optional_goals_total} optional
              </span>
              <Progress value={outcome.final_progress_percentage} />
            </div>
            <b>{outcome.final_progress_percentage}%</b>
            {outcome.succeeded ? (
              <Pill tone="good">
                <Check /> Kept it
              </Pill>
            ) : (
              <Pill tone="bad">Owes {formatPence(outcome.total_forfeit_pence)}</Pill>
            )}
          </div>
        ))}
      </section>

      {data.forfeits.length === 0 && (
        <Empty
          title="No forfeits"
          body="Everybody finished every required goal. That is the whole point."
        />
      )}
    </>
  )
}

function ForfeitRow({ line, counterparty }: { line: ForfeitLine; counterparty: string }) {
  return (
    <div className="admin-row">
      <b>{counterparty}</b>
      <span>{formatPence(line.amount_pence)}</span>
      <Pill tone={line.status === 'SETTLED' ? 'good' : 'warn'}>
        {line.status === 'SETTLED' ? 'Settled' : 'Outstanding'}
      </Pill>
    </div>
  )
}
