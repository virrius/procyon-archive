import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from './i18n'
import { Modal } from './ui'

/** Ctrl+V картинкой: снимок из буфера уходит тем же путём, что и выбранный файл.
 *  Слушателей на странице может быть несколько (карточка окном поверх галереи) —
 *  вставку забирает верхний, тот что смонтирован последним. */
type Handler = (files: File[]) => void

const stack: Handler[] = []

const typing = (node: any): boolean => {
  if (!node || !node.tagName) return false
  const tag = String(node.tagName).toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || !!node.isContentEditable
}

const onPaste = (ev: ClipboardEvent) => {
  const top = stack[stack.length - 1]
  if (!top) return
  // в поле ввода вставка остаётся текстовой
  if (typing(ev.target) || typing(document.activeElement)) return
  const files = Array.from(ev.clipboardData?.items || [])
    .filter(i => i.kind === 'file' && i.type.startsWith('image/'))
    .map(i => i.getAsFile())
    .filter(Boolean) as File[]
  if (!files.length) return
  ev.preventDefault()
  top(files)
}

const listen = (on: boolean) => {
  if (on) window.addEventListener('paste', onPaste)
  else window.removeEventListener('paste', onPaste)
}

export function usePasteImage(onFiles: Handler, enabled = true) {
  const latest = useRef(onFiles)
  latest.current = onFiles
  useEffect(() => {
    if (!enabled) return
    const entry: Handler = files => latest.current(files)
    stack.push(entry)
    if (stack.length === 1) listen(true)
    return () => {
      const i = stack.indexOf(entry)
      if (i >= 0) stack.splice(i, 1)
      if (!stack.length) listen(false)
    }
  }, [enabled])
}

const kb = (n: number) => (n < 1024 * 1024
  ? i18n.t('common:size_kb', { n: Math.max(1, Math.round(n / 1024)) })
  : i18n.t('common:size_mb', { n: (n / 1024 / 1024).toFixed(1) }))

/** Вставка спрашивает: показываем снимок из буфера и ждём «да». Случайный Ctrl+V
 *  чужой картинкой не затирает портрет. */
export default function PasteImage({ onFiles, enabled = true, title, question }: {
  onFiles: Handler
  enabled?: boolean
  /** заголовок окна и строка вопроса — что именно случится с картинкой */
  title?: string
  question?: string
}) {
  const { t } = useTranslation('common')
  const [ask, setAsk] = useState<File[] | null>(null)
  const [urls, setUrls] = useState<string[]>([])

  usePasteImage(files => setAsk(files), enabled)

  // предпросмотр живёт ровно столько, сколько открыто окно
  useEffect(() => {
    if (!ask) { setUrls([]); return }
    const made = ask.map(f => URL.createObjectURL(f))
    setUrls(made)
    return () => made.forEach(URL.revokeObjectURL)
  }, [ask])

  // окно закрылось вместе с блоком, который его поставил — файлы не всплывут потом
  useEffect(() => { if (!enabled) setAsk(null) }, [enabled])

  if (!ask) return null

  const many = ask.length > 1
  const take = () => { const files = ask; setAsk(null); onFiles(files) }

  return (
    <Modal title={title || (many ? t('paste.title_multi') : t('paste.title_single'))}
      onClose={() => setAsk(null)}>
      <div className="paste-ask">
        <div className="paste-shots">
          {urls.map((u, i) => (
            <figure key={u} className="paste-shot">
              <img src={u} alt={t('paste.alt', { n: i + 1 })} />
              <figcaption className="mono dim2 small">{kb(ask[i].size)}</figcaption>
            </figure>
          ))}
        </div>
        <div className="dim2 small">
          {question || (many
            ? t('paste.question_multi')
            : t('paste.question_single'))}
        </div>
        <div className="row">
          <div className="spacer" />
          <button type="button" className="ghost" onClick={() => setAsk(null)}>{t('no')}</button>
          <button type="button" className="primary" autoFocus onClick={take}>{t('paste.yes')}</button>
        </div>
      </div>
    </Modal>
  )
}
