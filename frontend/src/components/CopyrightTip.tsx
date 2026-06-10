import { HelpTip } from './HelpTip'

const COPYRIGHT_TOOLTIP =
  'Editions first published before 1923 are public domain in the United States and will be added to the Partifi Library.'

export function CopyrightTip() {
  return <HelpTip className="copyright-tip" text={COPYRIGHT_TOOLTIP} />
}
