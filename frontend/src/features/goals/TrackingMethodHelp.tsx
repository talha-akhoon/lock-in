import { TRACKING_HELP, TRACKING_HELP_INTRO } from '../../lib/help'
import { TRACKING_TYPES, type TrackingType } from '../../lib/types'

export function TrackingMethodHelp({ selected }: { selected?: TrackingType }) {
  return (
    <>
      <p>{TRACKING_HELP_INTRO}</p>
      <ul className="help-list">
        {TRACKING_TYPES.map((type) => {
          const item = TRACKING_HELP[type]
          return (
            <li key={type} className={type === selected ? 'current' : undefined}>
              <b>{item.title}</b>
              <span>{item.body}</span>
              <em>e.g. {item.example}</em>
            </li>
          )
        })}
      </ul>
    </>
  )
}
