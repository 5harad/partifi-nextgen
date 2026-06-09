import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { applyTagSelection, extractLast, filterTagAutocomplete } from '../../lib/segmentTagSuggestions'
import { formatTagsInput, formatTagsOnFocus } from '../../lib/segmentTags'

type Props = {
  value: string
  tagIsSuggestion: boolean
  tagList: string[]
  style: React.CSSProperties
  onValueChange: (value: string, tagIsSuggestion: boolean) => void
  onAfterChange: () => void
  onFocusStart?: () => void
  onFocusEnd?: () => void
  onTabNext: () => void
  inputRef?: (el: HTMLInputElement | null) => void
  suppressBlurRef?: React.RefObject<boolean>
  onClearClick?: () => void
}

export function TagsInput({
  value,
  tagIsSuggestion,
  tagList,
  style,
  onValueChange,
  onAfterChange,
  onFocusStart,
  onFocusEnd,
  onTabNext,
  inputRef,
  suppressBlurRef,
  onClearClick,
}: Props) {
  const listId = useId()
  const inputEl = useRef<HTMLInputElement | null>(null)
  const menuRef = useRef<HTMLUListElement | null>(null)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({})
  const [options, setOptions] = useState<string[]>([])

  const tagClass = tagIsSuggestion ? 'tags suggestions' : 'tags'

  const updateMenuPosition = () => {
    const el = inputEl.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    setMenuStyle({
      position: 'fixed',
      left: rect.left,
      top: rect.bottom,
      minWidth: rect.width,
      zIndex: 3000,
    })
  }

  const refreshOptions = (term: string) => {
    const last = extractLast(term)
    if (last.length < 1) {
      setOptions([])
      setOpen(false)
      return
    }
    const matches = filterTagAutocomplete(tagList, last)
    setOptions(matches)
    setActiveIndex(0)
    setOpen(matches.length > 0)
  }

  useLayoutEffect(() => {
    if (open) updateMenuPosition()
  }, [open, options])

  useEffect(() => {
    if (!open) return
    const onScrollOrResize = () => updateMenuPosition()
    window.addEventListener('scroll', onScrollOrResize, true)
    window.addEventListener('resize', onScrollOrResize)
    return () => {
      window.removeEventListener('scroll', onScrollOrResize, true)
      window.removeEventListener('resize', onScrollOrResize)
    }
  }, [open])

  useEffect(() => {
    const onDocMouseDown = (e: MouseEvent) => {
      const target = e.target as Node
      if (inputEl.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [])

  const selectOption = (selected: string) => {
    const next = applyTagSelection(value, selected)
    onValueChange(next, false)
    setOpen(false)
    onAfterChange()
    inputEl.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Tab') {
      if (!open) {
        e.preventDefault()
        onTabNext()
      }
      return
    }

    if (!open || options.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => (i + 1) % options.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => (i - 1 + options.length) % options.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      selectOption(options[activeIndex])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const menu =
    open && options.length > 0
      ? createPortal(
          <ul
            ref={menuRef}
            id={listId}
            className="ui-autocomplete ui-menu ui-widget ui-widget-content"
            role="listbox"
            style={menuStyle}
          >
            {options.map((option, idx) => (
              <li key={option} className="ui-menu-item" role="presentation">
                <a
                  href="#"
                  className={`ui-corner-all${idx === activeIndex ? ' ui-state-hover' : ''}`}
                  role="option"
                  aria-selected={idx === activeIndex}
                  onMouseDown={(ev) => ev.preventDefault()}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={(ev) => {
                    ev.preventDefault()
                    selectOption(option)
                  }}
                >
                  {option}
                </a>
              </li>
            ))}
          </ul>,
          document.body,
        )
      : null

  return (
    <>
      <input
        ref={(el) => {
          inputEl.current = el
          inputRef?.(el)
        }}
        className={tagClass}
        value={value}
        style={style}
        onChange={(e) => {
          let next = e.target.value
          if (tagIsSuggestion) {
            if (value && next.startsWith(value)) {
              next = next.slice(value.length)
            } else {
              next = extractLast(next)
            }
          } else if (value === '(none)' && next !== '(none)') {
            next = next.replace(/^\(none\),?\s*/, '')
          }
          onValueChange(next, false)
          refreshOptions(next)
        }}
        onKeyDown={handleKeyDown}
        onMouseDown={(e) => {
          const el = e.currentTarget
          const clickX = e.clientX - el.getBoundingClientRect().left
          if (clickX > el.clientWidth - 22 && onClearClick) {
            e.preventDefault()
            if (suppressBlurRef) suppressBlurRef.current = true
            onClearClick()
          }
        }}
        onBlur={() => {
          onFocusEnd?.()
          if (suppressBlurRef?.current) {
            suppressBlurRef.current = false
            setOpen(false)
            return
          }
          onValueChange(formatTagsInput(value), false)
          setOpen(false)
          onAfterChange()
        }}
        onFocus={() => {
          onFocusStart?.()
          if (tagIsSuggestion) {
            onValueChange('', false)
            refreshOptions('')
          } else if (value) {
            const formatted = formatTagsOnFocus(value)
            onValueChange(formatted, false)
            refreshOptions(formatted)
          } else {
            refreshOptions('')
          }
        }}
        onClick={() => {
          if (value === '(none)') {
            inputEl.current?.select()
          }
        }}
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
      />
      {menu}
    </>
  )
}
