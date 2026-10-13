import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, store, type Dict } from '../api'
import { lang } from '../i18n'

/** Campaign transfer: the archive is built and unpacked on the server in the background; here, the progress. */

export type Job = Dict & { id: string; status: 'running' | 'done' | 'failed'; stage: string; done: number; total: number }

const mb = (n: number) => (n / 1048576).toFixed(n < 10 * 1048576 ? 1 : 0)

/** Poll the task while it runs. */
export function useJob(onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null)
  const done = useRef(onDone)
  done.current = onDone
  useEffect(() => {
    if (!job || job.status !== 'running' || job.stage === 'upload') return
    const timer = setTimeout(async () => {
      try {
        const next: Job = await api.get(`/api/admin/transfers/${job.id}`)
        setJob(next)
        if (next.status === 'done') done.current?.(next)
      } catch (e: any) { setJob({ ...job, status: 'failed', error: e.message }) }
    }, 400)
    return () => clearTimeout(timer)
  }, [job])
  return [job, setJob] as const
}

export function TransferBar({ job }: { job: Job }) {
  const { t } = useTranslation('admin')
  if (job.status === 'failed') return <div className="xfer-err">{t('xfer.failed', { error: job.error })}</div>
  const bytes = job.stage === 'files' || job.stage === 'upload'
  const pct = job.total ? Math.min(100, Math.round((job.done / job.total) * 100)) : null
  const count = job.total && job.status === 'running'
    ? (bytes ? t('xfer.mb', { done: mb(job.done), total: mb(job.total) }) : `${job.done} / ${job.total}`)
    : ''
  return (
    <div className={`xfer${job.status === 'done' ? ' ok' : ''}`}>
      <div className="xfer-line">
        <span>{t(`xfer.stage.${job.stage}`)}</span>
        <span className="mono dim">{count}{pct !== null && job.status === 'running' ? ` · ${pct}%` : ''}</span>
      </div>
      <div className={`xfer-track${pct === null && job.status === 'running' ? ' busy' : ''}`}>
        <i style={{ width: `${job.status === 'done' ? 100 : pct ?? 0}%` }} />
      </div>
    </div>
  )
}

/** The browser downloads the finished archive itself: the token cookie lets it reach the file URL. */
export function download(job: Job) {
  const a = document.createElement('a')
  a.href = `/api/admin/transfers/${job.id}/file`
  a.download = job.download || ''
  document.body.appendChild(a)
  a.click()
  a.remove()
}

/** The archive goes as the request body: upload progress is shown in bytes. */
export function upload(file: File, onProgress: (done: number, total: number) => void): Promise<Job> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/admin/campaigns/import')
    xhr.setRequestHeader('Authorization', `Bearer ${store.token}`)
    xhr.setRequestHeader('Accept-Language', lang())
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name))
    xhr.upload.onprogress = e => onProgress(e.loaded, e.total || file.size)
    xhr.onload = () => {
      let body: any = null
      try { body = JSON.parse(xhr.responseText) } catch { /* noop */ }
      if (xhr.status >= 200 && xhr.status < 300 && body) resolve(body)
      else reject(new Error(body?.detail || xhr.statusText || String(xhr.status)))
    }
    xhr.onerror = () => reject(new Error(xhr.statusText || 'network error'))
    xhr.send(file)
  })
}
