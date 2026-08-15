import { STEP_HELP_BODY, STEP_HELP_TITLE, STEP_HELP_WHEN } from '../../lib/help'

export function StepHelp() {
  return (
    <>
      <p>
        <b>{STEP_HELP_TITLE}</b> {STEP_HELP_BODY}
      </p>
      <p>{STEP_HELP_WHEN}</p>
    </>
  )
}
