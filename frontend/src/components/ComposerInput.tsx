import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { filterComposerNames, loadComposerData } from '../lib/composerAutocomplete'

type Props = {
  id: string
  className?: string
  value: string
  onChange: (value: string) => void
  minLength?: number
}

export function ComposerInput({ id, className, value, onChange, minLength = 2 }: Props) {
  const listId = useId()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const menuRef = useRef<HTMLUListElement | null>(null)
  const [names, setNames] = useState<string[]>([])
  const [popular, setPopular] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({})
  const [options, setOptions] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    loadComposerData()
      .then((data) => {
        if (!cancelled) {
          setNames(data.names)
          setPopular(data.popular)
        }
      })
      .catch(() => {
        /* autocomplete is optional; free-text input still works */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const updateMenuPosition = () => {
    const el = inputRef.current
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
    if (term.trim().length < minLength || names.length === 0) {
      setOptions([])
      setOpen(false)
      return
    }
    const matches = filterComposerNames(names, term, popular)
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
      if (inputRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [])

  const selectOption = (selected: string) => {
    onChange(selected)
    setOpen(false)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
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
        ref={inputRef}
        id={id}
        type="text"
        className={className}
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          refreshOptions(e.target.value)
        }}
        onKeyDown={handleKeyDown}
        onFocus={() => refreshOptions(value)}
        onBlur={() => setOpen(false)}
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
      />
      {menu}
    </>
  )
}
