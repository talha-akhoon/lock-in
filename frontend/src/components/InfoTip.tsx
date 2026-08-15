import { CircleHelp } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

export function InfoTip({
  label,
  heading,
  children,
}: {
  /** Accessible name for the button, e.g. "About tracking methods". */
  label: string
  /** When set, the button sits on the same row as this field name. */
  heading?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return

    function onPointer(event: PointerEvent) {
      if (root.current && !root.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      // Close this panel first; do not let the parent modal swallow Escape.
      event.stopImmediatePropagation()
      setOpen(false)
    }

    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey, true)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey, true)
    }
  }, [open])

  const button = (
    <button
      type="button"
      className="info-tip-button"
      aria-label={label}
      aria-expanded={open}
      aria-controls={panelId}
      onClick={() => setOpen((value) => !value)}
    >
      <CircleHelp />
    </button>
  )

  return (
    <div className={heading ? 'info-tip with-heading' : 'info-tip'} ref={root}>
      {heading ? (
        <div className="field-head">
          <span>{heading}</span>
          {button}
        </div>
      ) : (
        button
      )}
      {open && (
        <div className="info-tip-panel" id={panelId} role="note">
          {children}
        </div>
      )}
    </div>
  )
}
