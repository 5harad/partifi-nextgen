type Props = {
  text: string
  className?: string
}

export function HelpTip({ text, className }: Props) {
  return (
    <div className={className ? `help-tip ${className}` : 'help-tip'} tabIndex={0} aria-label={text}>
      <span className="help-tip-popup" role="tooltip">
        {text}
      </span>
    </div>
  )
}
