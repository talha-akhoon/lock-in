import { TRACKING_HELP, TRACKING_HELP_INTRO, trackingExample } from '../../lib/help'
import { TRACKING_TYPES, type Category, type TrackingType } from '../../lib/types'

export function TrackingMethodHelp({
  selected,
  category,
}: {
  selected?: TrackingType
  category?: Category
}) {
  return (
    <>
      <p>{TRACKING_HELP_INTRO}</p>
      <ul className="help-list">
        {TRACKING_TYPES.map((type) => {
          const item = TRACKING_HELP[type]
          return (
            <li key={type} className={type === selected ? 'current' : undefined}>
              <b>{item.title}</b>
              <span>{item.checkin}</span>
              <span>{item.avoid}</span>
              <em>e.g. {trackingExample(type, category)}</em>
            </li>
          )
        })}
      </ul>
    </>
  )
}
