type Props = {
  message: string
  progress?: number
  indeterminate?: boolean
}

export function TransitionWait({ message, progress = 0, indeterminate = false }: Props) {
  const ribbonWidth = progress * 4 + 20

  return (
    <div id="main" style={{ height: '750px' }}>
      <img
        src="/images/notes_bg.jpg"
        width={1190}
        height={252}
        style={{ position: 'absolute', left: 0, top: 200, zIndex: -1, opacity: 0.3 }}
        alt=""
      />
      <div id="transition">
        <div id="transition-text">{message}</div>
        <div id="progress-bar" className={indeterminate ? 'progress-indeterminate' : undefined}>
          <div id="progress-ribbon" style={indeterminate ? undefined : { width: ribbonWidth }} />
        </div>
      </div>
    </div>
  )
}
