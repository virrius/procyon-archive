import { Fragment, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, c as camp, type Dict } from '../../api'
import { useApp } from '../../ctx'
import { asList } from '../../ui'
import { dict, list, num, readContacts } from '../sheet/parts'
import { type Ctx } from './lanes'
import { ACT_MAX, type Attr, rating, talentKey, talentOf } from './model'
import '../../styles.dossier.css'

/* значения бланка в обоих языках → ключи формулировок досье */
const TRAITS: Dict = {
  'Визионер': 'haunted', 'Маньяк': 'obsessed', 'Параноик': 'paranoid', 'Псих': 'unstable',
  'Раздолбай': 'reckless', 'Садист': 'vicious', 'Социопат': 'cold', 'Тряпка': 'soft',
  Haunted: 'haunted', Obsessed: 'obsessed', Paranoid: 'paranoid', Unstable: 'unstable',
  Reckless: 'reckless', Vicious: 'vicious', Cold: 'cold', Soft: 'soft',
}
const VICES: Dict = {
  'Азартные игры': 'gambling', 'Беспамятство': 'stupor', 'Долг': 'obligation', 'Наслаждения': 'pleasure',
  'Потустороннее': 'weird', 'Религия': 'faith', 'Роскошь': 'luxury',
  Gambling: 'gambling', Stupor: 'stupor', Obligation: 'obligation', Pleasure: 'pleasure',
  Weird: 'weird', Faith: 'faith', Luxury: 'luxury',
}
const HEAT_HIGH = 5

/** Ключ строки → число для выбора дознавателя: одно дело — один подписант. */
// листов в описи имущества по уровню жизни, разброс ±25%
const ASSET_PAGES = [2, 5, 18, 184]
const pick = (id: string, n: number) => [...id].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7) % n

/** k разных номеров из n — по ключу дела. */
const several = (key: string, n: number, k: number) => {
  const out: number[] = []
  for (let i = 0; out.length < Math.min(k, n); i++) {
    const v = pick(key + i, n)
    if (!out.includes(v)) out.push(v)
  }
  return out
}

/** Вставки вразброс между элементами списка (не перед первым) — места по ключу дела. */
function scatter<T>(key: string, base: T[], extra: T[]): T[] {
  const out = [...base]
  extra.forEach((x, j) => out.splice(1 + pick(key + j, out.length), 0, x))
  return out
}

/** «Досье» — личное дело из реестра: только то, что держится дольше сцены. Анкета, резюме
 *  дознавателя, описание, психопрофиль, розыск экипажа, подготовка, связи, организации, приложения.
 *  Скрытое от игрока — вымарано. */
export function DossierFile({ c, id, name, alias, photo, texts, status, rev, npcs }: {
  c: Ctx; id: string; name: string; alias: string; photo: ReactNode; texts: ReactNode
  status: string; rev: string; npcs: Dict[]
}) {
  const { t } = useTranslation('char')
  const { isGM } = useApp()
  const [ship, setShip] = useState<Dict | null>(null)
  const [factions, setFactions] = useState<Dict[]>([])
  useEffect(() => {
    let alive = true
    api.get(`${camp()}/entities?kind=ship`)
      .then(r => { if (alive) setShip((Array.isArray(r) ? r : []).find((x: Dict) => x.kind === 'ship') || null) })
      .catch(() => { if (alive) setShip(null) })
    api.get(`${camp()}/entities?kind=faction`)
      .then(r => { if (alive) setFactions(Array.isArray(r) ? r : []) })
      .catch(() => { if (alive) setFactions([]) })
    return () => { alive = false }
  }, [])

  const f = c.f
  const caseNo = id.replace(/-/g, '').slice(0, 8).toUpperCase().replace(/^(.{4})/, '$1-')
  const shipName = String(ship?.name || '')
  const book = c.book
  const role = !c.locked('playbook') && book ? t(`dos.role.${c.pb}`, { defaultValue: book.label.toLowerCase() }) : ''

  // розыск экипажа по системам: уровень и подозрения
  const heat = dict(ship?.fields?.heat)
  const systems = Object.keys(heat)
    .map(s => ({ s, wanted: Math.min(4, num(heat[s]?.wanted)), hot: num(heat[s]?.heat) >= HEAT_HIGH }))
    .filter(x => x.wanted > 0 || x.hot)
    .sort((a, b) => b.wanted - a.wanted || Number(b.hot) - Number(a.hot))
  const topWanted = systems.reduce((m, x) => Math.max(m, x.wanted), 0)
  const [stamp, tone] = status === 'dead' ? ['closed', 'end']
    : status === 'retired' ? ['retired', 'end']
    : topWanted >= 4 ? ['intercept', 'dead']
    : topWanted >= 2 ? ['wanted', 'dead']
    : topWanted === 1 || systems.length ? ['watch', 'warn']
    : ['free', 'ok']

  const known = (field: string, map: Dict) => (c.locked(field) ? null : asList(f[field]).map(v => ({ v, k: map[v] || '' })))
  const traits = known('trauma', TRAITS)
  const vices = known('vice', VICES)
  const attrs: Attr[] = Array.isArray(c.sheet.attributes) ? c.sheet.attributes : []
  const acts = dict(f.actions)
  const strong = attrs.flatMap(a => a.actions).filter(x => num(acts[x.key]) >= ACT_MAX).map(x => x.name.toLowerCase())
  const untrained = attrs.length > 0 && attrs.every(a => a.actions.every(x => !num(acts[x.key])))
  const total = attrs.reduce((n, a) => n + rating(a, acts), 0)
  const threat = total <= 2 ? 0 : total <= 5 ? 1 : total <= 8 ? 2 : 3

  const ties = c.locked('contacts') ? null : readContacts(f.contacts)
    .map(r => ({ ...r, name: String(npcs.find(n => n.id === r.entity_id)?.name || '') }))
    .filter(r => r.name)
  // отношение организаций Гегемонии и синдикатов к экипажу: союз и вражда от ±2; отметки сделанных для них дел
  const orgs = factions
    .filter(e => ['hegemony', 'criminal'].includes(String(e.fields?.category || '')))
    .map(e => ({
      name: String(e.name || ''),
      rank: !isGM && list(e.hidden_fields).includes('rank') ? 0 : num(e.fields?.rank),
      stance: Math.max(-3, Math.min(3, Math.trunc(Number(e.fields?.stance) || 0))),
      deeds: Array.isArray(e.fields?.deeds) ? e.fields.deeds.length : 0,
    }))
    .filter(x => x.name)
  const standing = orgs.filter(x => Math.abs(x.stance) >= 2).sort((a, b) => a.stance - b.stance)
  const served = orgs.filter(x => x.deeds > 0).sort((a, b) => b.deeds - a.deeds)
  const tiers: any[] = Array.isArray(c.sheet.stash) ? c.sheet.stash : []
  const stash = num(f.stash)
  const tier = tiers.findIndex((r: any[]) => stash >= num(r[0]) && stash <= num(r[1]))

  const taken = list(f.talents)
  const own = c.eff.talents.map(x => ({ ...x, key: talentKey(c.pb, x.key) }))
  const ownKeys = new Set(own.map(x => x.key))
  const talents = [
    ...own.filter(x => taken.includes(x.key)),
    ...taken.filter(k => !ownKeys.has(k)).map(k => talentOf(c.meta, c.setup, k) || { key: k, name: k, text: '' }),
  ]
  const unique = f.xeno
    ? { name: t('unique.xeno'), text: String(f.xeno_text || '') }
    : book && { name: book.unique.name, text: t(`dos.mark.${c.pb}.unique`, { defaultValue: book.unique.text || '' }) }
  // наблюдение дознавателя вместо правил; своей способности ГМа в словаре нет — её текст
  const mark = (key: string, text: string) => t(`dos.mark.${key.replace(':', '.')}`, { defaultValue: text })

  const names: string[] = t('dos.investigators', { returnObjects: true }) as any
  const ranks: string[] = t('dos.ranks', { returnObjects: true }) as any
  const signer = Array.isArray(names) && names.length ? names[pick(id, names.length)] : ''
  const rank = Array.isArray(ranks) && ranks.length ? ranks[pick(id + 'r', ranks.length)] : ''

  const traitName = (x: { v: string; k: string }) => (x.k ? t(`dos.trait.${x.k}.name`) : x.v.toLowerCase())
  const viceName = (x: { v: string; k: string }) => (x.k ? t(`dos.vice.${x.k}.name`) : x.v.toLowerCase())
  const heritage = c.locked('heritage') ? '' : asList(f.heritage).join(', ')
  const past = c.locked('past') ? '' : asList(f.past).join(', ')
  const sys = (x: { s: string; wanted: number }) => `${x.s} — ${t(`dos.wanted.${x.wanted}`)}`
  // организации в резюме: три самые сильные по рангу, война и «свои» — даже вне тройки
  const brief = (label: string, xs: typeof orgs, fmt: (x: (typeof orgs)[number]) => string, sep: string) => {
    const ranked = [...xs].sort((a, b) => b.rank - a.rank || Math.abs(b.stance) - Math.abs(a.stance) || b.deeds - a.deeds)
    const shown = [...ranked.slice(0, 3), ...ranked.slice(3).filter(x => Math.abs(x.stance) === 3)]
    const more = xs.length > shown.length
    return `${label}: ${shown.map(fmt).join(sep)}${more ? ` ${t('dos.res.etc')}` : '.'}`
  }

  const size = (key: string) => {
    const v = t(key, { returnObjects: true })
    return v && typeof v === 'object' ? Object.keys(v).length : 0
  }
  const secretLines = several(id + 's', size('dos.res.secret'), 1 + pick(id + 'c', 2))
    .map(k => <Redacted text={t(`dos.res.secret.${k}`, { n: 10 + pick(id + 'n' + k, 89) })} />)
  const resume: ReactNode[][] = [[
    t(shipName ? 'dos.res.who' : 'dos.res.who_noship', {
      name: name || t('dos.res.noname'), alias: alias ? t('dos.res.alias', { alias }) : '', role: role || t('dos.role.none'), ship: shipName,
    }),
    heritage && past ? t('dos.res.origin_past', { heritage, past })
      : heritage ? t('dos.res.origin', { heritage }) : past ? t('dos.res.past', { past }) : '',
    traits && (traits.length
      ? <>{t('dos.res.psy')}: <em>{traits.map(traitName).join(', ')}</em>.</>
      : t('dos.res.psy_none')),
    vices && vices.length > 0 && `${t('dos.res.leverage')}: ${vices.map(viceName).join(', ')}.`,
    strong.length ? `${t('dos.res.strong')}: ${strong.join(', ')}.` : untrained ? t('dos.res.untrained') : '',
  ], [
    standing.length > 0 && brief(t('dos.res.orgs'), standing, x => `${x.name} — ${t(`dos.stance.${x.stance}`)}`, '; '),
    served.length > 0 && brief(t('dos.res.served'), served, x => `${x.name} (${x.deeds})`, ', '),
  ], [
    systems.some(x => x.hot) && <>{t('dos.res.heat')}: <em>{systems.filter(x => x.hot).map(x => x.s).join(', ')}</em>.</>,
    systems.some(x => x.wanted)
      ? `${t('dos.res.wanted')}: ${systems.filter(x => x.wanted).map(sys).join('; ')}.`
      : t('dos.res.wanted_none'),
    <>{t('dos.res.threat')}: <b>{t(`dos.threat.${threat}`)}</b>.</>,
  ]].map(p => p.filter(Boolean)).filter(p => p.length)
  secretLines.forEach((x, j) => {
    const n = pick(id + 'g' + j, resume.length)
    resume[n] = scatter(id + 'p' + j, resume[n], [x])
  })
  const rec = !c.locked('playbook') && book ? t(`dos.rec.${c.pb}`, { defaultValue: '' }) : ''

  const row = (k: ReactNode, v: ReactNode, cls = '', key?: string) => (
    <div key={key} className="cs-ff"><span className="k">{k}</span><span className="dots" /><span className={`v ${cls}`}>{v}</span></div>
  )
  const idCell = (label: string, v: ReactNode, note = '') => (
    <div>
      <dt>{label}</dt>
      <dd><b>{v}</b>{note && <IdNote text={note} />}</dd>
    </div>
  )
  const note = (field: string) => (c.locked(field) ? '' : String(f[`${field}_note`] || '').trim())
  const docs = scatter<{ key: string; secret?: number }>(id + 'q',
    ['assets', 'contacts', 'watch', 'money', 'mail', 'medical'].map(key => ({ key })),
    several(id + 'a', size('dos.annex_secret'), 2 + pick(id + 'k', 2)).map(k => ({ key: `s${k}`, secret: k })))
  const red = (key: string) => <Red w={7 + pick(id + key, 7)} />
  const pages = (key: string) => (key === 'assets' && tier >= 0 && !c.locked('stash')
    ? Math.max(1, Math.round(ASSET_PAGES[Math.min(tier, ASSET_PAGES.length - 1)] * (0.75 + pick(id + 'assets%', 1001) / 2000)))
    : pick(id + key, 9) + 1)

  return (
    <section className="cs-file" data-sec="dossier">
      <div className="cs-file-tab">
        <b>{t('dos.dept')}</b>
        <span>{t('dos.office')}</span>
        <span>{t('dos.registry')}{shipName && ` · «${shipName}»`}</span>
        <span className="r">
          {t('dos.form')} · {t('dos.case', { id: caseNo })}{rev && ` · ${t('dos.rev', { date: rev })}`} · <span className="grif">{t('dos.grif')}</span>
        </span>
      </div>
      <div className="cs-file-b">
        <div className="cs-file-head">
          <figure className="cs-file-photo">
            {photo}
            <figcaption>{t('dos.photo')}</figcaption>
          </figure>
          <div className="cs-file-who">
            <h2 className="cs-file-name">{name || t('dos.res.noname')}</h2>
            {alias && <div className="cs-file-aka">{t('dos.aka', { alias })}</div>}
            <div className={`cs-stamp t-${tone}`}>{t(`dos.stamp.${stamp}`)}</div>
          </div>
          <dl className="cs-fid">
            {idCell(t('dos.id.heritage'), c.locked('heritage') ? red('heritage') : heritage || '—', note('heritage'))}
            {idCell(t('dos.id.past'), c.locked('past') ? red('past') : past || '—', note('past'))}
            {idCell(t('dos.id.role'), c.locked('playbook') ? red('playbook') : role || '—')}
          </dl>
        </div>

        <div className="cs-fbody">
          <div className="cs-fsec cs-fres">
            <h3>{t('dos.sec.resume')}</h3>
            {resume.map((p, n) => (
              <p key={n} className="cs-resume">{p.map((x, i) => <Fragment key={i}>{i > 0 && ' '}{x}</Fragment>)}</p>
            ))}
            {rec && <p className="cs-resume">{t('dos.res.rec')}: {rec}</p>}
            {signer && (
              <div className="cs-sign">
                <span>{rank} {signer}</span>
                <span className="line" />
                <span className="sig">{signer.split(' ').pop()}</span>
              </div>
            )}
          </div>

          <div className="cs-fsec cs-fdesc">
            <h3>{t('dos.sec.description')}</h3>
            {texts}
          </div>

          <div className="cs-fsec cs-fpsy">
            <h3>{t('dos.sec.psy')}</h3>
            <div className="ss-cap">{t('dos.psy.traits')}</div>
            {!traits ? <div className="cs-fnote">{red('trauma')}</div>
              : traits.length ? traits.map(x => (
                  <div key={x.v} className="cs-fnote"><b>{traitName(x)}</b>{x.k && <> — {t(`dos.trait.${x.k}.text`)}.</>}</div>
                ))
              : <div className="cs-fnote">{t('dos.psy.none')}</div>}
            <div className="ss-cap">{t('dos.psy.leverage')}</div>
            {!vices ? <div className="cs-fnote">{red('vice')}</div>
              : vices.length ? vices.map((x, i) => (
                  <div key={x.v} className="cs-fnote">
                    <b>{viceName(x)}</b>{x.k && <> — {t(`dos.vice.${x.k}.text`)}.</>}
                    {i === 0 && note('vice') && <IdNote text={t('dos.psy.observed', { note: note('vice') })} />}
                  </div>
                ))
              : <div className="cs-fnote">—</div>}
          </div>

          {unique && (
            <div className="cs-fsec cs-fmarks">
              <h3>{t('dos.sec.marks')}</h3>
              <div className="cs-fnote"><b>{unique.name}.</b> {unique.text}</div>
              {talents.map(x => <div key={x.key} className="cs-fnote"><b>{x.name}.</b> {mark(x.key, x.text || '')}</div>)}
            </div>
          )}

          <div className="cs-fdata">
            <div className="cs-fsec cs-fwant">
              <h3>{t('dos.sec.wanted')}</h3>
              {systems.length
                ? systems.map(x => (
                    <Fragment key={x.s}>
                      {row(x.s, <>
                        <span className="cs-flvl">{Array.from({ length: 4 }, (_, i) => <i key={i} className={i < x.wanted ? 'on' : ''} />)}</span>
                        {t(`dos.wanted.${x.wanted}`)}
                      </>, x.wanted >= 2 ? 'rust' : '')}
                      {x.hot && <div className="cs-fsub rust">{t('dos.heat_high')}</div>}
                    </Fragment>
                  ))
                : row(t('dos.all_systems'), t('dos.wanted_none'), 'dim')}
              {shipName && <div className="cs-fsub left">{t('dos.crew_case', { ship: shipName })}</div>}
            </div>

            {book && attrs.length > 0 && (
              <div className="cs-fsec">
                <h3>{t('dos.sec.training')}</h3>
                <div className="cs-fgrid">
                  {attrs.map(a => (
                    <div key={a.key} className="cs-fattr">
                      {row(a.name.toLowerCase(), rating(a, acts))}
                      {a.actions.map(x => {
                        const v = Math.min(ACT_MAX, num(acts[x.key]))
                        return row(x.name.toLowerCase(), t(`dos.train.${v}`), v === 0 ? 'dim' : v >= ACT_MAX ? 'top' : '', x.key)
                      })}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="cs-fsec">
              <h3>{t('dos.sec.ties')}</h3>
              {!ties ? <div className="cs-fnote">{red('contacts')}</div>
                : ties.length ? ties.map(r => row(r.name, t(`dos.tie.${r.state}`),
                    r.state === 'rival' ? 'rust' : r.state === 'friend' ? '' : 'dim', r.entity_id))
                : row(t('dos.ties_k'), t('dos.ties_none'), 'dim')}
            </div>

            <div className="cs-fsec cs-forgs">
              <h3>{t('dos.sec.orgs')}</h3>
              {standing.map(x => row(x.name, t(`dos.stance.${x.stance}`), x.stance < 0 ? 'rust' : '', `s-${x.name}`))}
              {served.length > 0 && <div className="ss-cap">{t('dos.served')}</div>}
              {served.map(x => row(x.name, t('dos.deeds', { count: x.deeds }), '', `d-${x.name}`))}
              {!standing.length && !served.length && row(t('dos.orgs_k'), t('dos.orgs_none'), 'dim')}
            </div>

            {tier >= 0 && !c.locked('stash') && (
              <div className="cs-fsec">
                <h3>{t('dos.sec.wealth')}</h3>
                {row(t('dos.life'), t(`dos.tier.${tier}.name`, { defaultValue: String(tiers[tier][2]).split(':')[0] }))}
                <div className="cs-fsub">{t(`dos.tier.${tier}.text`, { defaultValue: '' })}</div>
              </div>
            )}

            <div className="cs-fsec">
              <h3>{t('dos.sec.annex')}</h3>
              <ol className="cs-annex">
                {docs.map(d => (
                  <li key={d.key}>
                    {d.secret === undefined
                      ? <>
                          <span className="doc" title={t('dos.annex_locked')}>{t(`dos.annex.${d.key}`)}</span>
                          <span className="pp">{t('dos.annex_pp', { n: pages(d.key) })}</span>
                        </>
                      : <>
                          <span className="doc" title={t('dos.annex_locked')}>
                            <Redacted text={t(`dos.annex_secret.${d.secret}`, { n: 10 + pick(id + d.key, 89) })} />
                          </span>
                          <span className="pp seized">
                            <Redacted text={t(`dos.annex_seized.${pick(id + d.key + 'z', size('dos.annex_seized'))}`)} />
                          </span>
                        </>}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/** Вымаранное: плашка вместо скрытого от игрока или засекреченного. */
function Red({ w }: { w: number }) {
  const { t } = useTranslation('char')
  return <span className="cs-red" role="img" aria-label={t('dos.redacted')} title={t('dos.redacted')} style={{ width: `${w}ch` }} />
}

/** Текст с вымаранными местами: каждая серия «█» — плашка той же длины. */
function Redacted({ text }: { text: string }) {
  return <>{text.split(/(█+[.,;:»”)]?)/).map((p, i) => (p.startsWith('█')
    ? <span key={i} className="cs-red-g"><Red w={p.replace(/[^█]/g, '').length} />{p.replace(/█+/, '')}</span>
    : p))}</>
}

/** Заметка к анкете: длинная сворачивается до трёх строк. */
function IdNote({ text }: { text: string }) {
  const { t } = useTranslation('sheet')
  const box = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [over, setOver] = useState(false)
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const check = () => setOver(el.scrollHeight > el.clientHeight + 1)
    check()
    const ro = new ResizeObserver(check)
    ro.observe(el)
    return () => ro.disconnect()
  }, [text, open])
  return (
    <div className="cs-fid-note">
      <div ref={box} className={open ? '' : 'cut'}>{text}</div>
      {(over || open) && (
        <button type="button" className="cs-fid-more" aria-expanded={open} onClick={() => setOpen(!open)}>
          {t('more')} {open ? '−' : '+'}
        </button>
      )}
    </div>
  )
}
