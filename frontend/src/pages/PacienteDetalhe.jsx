import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { EIXO_A_LABELS, IDENTIFICACAO_CAMPOS, AGENTE_SECOES, labelFor } from '../caseModel'

const COMPLEXITY_BADGE = { baixa: 'badge-green', media: 'badge-amber', alta: 'badge-red' }

const EIXO_B_LABELS = { colaborativo: 'Colaborativo', ansioso: 'Ansioso', resistente: 'Resistente', confuso: 'Confuso', minimizador: 'Minimizador' }
const EIXO_C_LABELS = {
  baixo_letramento_vulneravel: 'Baixo letramento / vulnerável', medio_letramento_media: 'Letramento médio / classe média',
  alto_letramento_bom_acesso: 'Alto letramento / bom acesso', pediatrico: 'Pediátrico',
}
const NIVEL = { baixo: 'Baixo', baixa: 'Baixa', medio: 'Médio', media: 'Média', alto: 'Alto', alta: 'Alta' }

function Field({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  let display
  if (Array.isArray(value)) {
    if (value.length === 0) return null
    display = value.join(', ')
  } else if (typeof value === 'object') {
    display = JSON.stringify(value)
  } else {
    display = String(value)
  }
  if (!display.trim()) return null
  return (
    <div className="detail-pair">
      <dt>{label}</dt>
      <dd>{display}</dd>
    </div>
  )
}

function SectionHeader({ title }) {
  return <div className="detail-section">{title}</div>
}

function TextBlock({ text }) {
  if (!text?.trim()) return null
  return (
    <p style={{ margin: '0 0 12px', fontSize: 13.5, color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
      {text}
    </p>
  )
}

export default function PacienteDetalhe() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [patient, setPatient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const { user } = useAuth()

  useEffect(() => {
    client.get(`/kb/patients/${id}`)
      .then(r => setPatient(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Paciente não encontrado'))
      .finally(() => setLoading(false))
  }, [id])

  const backBtn = (
    <button className="btn btn-outline mb-24" onClick={() => navigate(-1)} style={{ gap: 6 }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
      </svg>
      Voltar para Pacientes
    </button>
  )

  if (loading) return (
    <Layout title="Paciente">
      <div className="loading-wrap"><div className="spinner"/><span>Carregando paciente...</span></div>
    </Layout>
  )

  if (error) return (
    <Layout title="Erro">
      {backBtn}
      <div className="alert alert-error">{error}</div>
    </Layout>
  )

  async function handleDelete() {
    const label = patient.nome || `caso #${patient.case_number}`
    if (!window.confirm(`Excluir permanentemente "${label}"? Sessões e relatórios de avaliação deste paciente também serão removidos. Esta ação não pode ser desfeita.`)) return
    setDeleting(true)
    try {
      await client.delete(`/kb/patients/${id}`)
      navigate('/pacientes', { replace: true })
    } catch (e) {
      setDeleting(false)
      window.alert(e.response?.data?.detail || 'Não foi possível excluir o paciente.')
    }
  }

  // ── Top-level patient fields ──────────────────────────────────────────
  const nome      = patient.nome || 'Paciente Virtual'
  const compKey    = (patient.complexidade || '').toLowerCase()
  const areaLabel  = EIXO_A_LABELS[patient.eixo_a] || patient.eixo_a
  const sexoLabel  = patient.sexo === 'M' ? 'Masculino' : patient.sexo === 'F' ? 'Feminino' : patient.sexo

  // ── case_data fields ──────────────────────────────────────────────────
  const cd    = patient.case_data || {}
  const ident = cd.identificacao   || {}
  const hda   = cd.historia_doenca_atual || ''
  const ic    = cd.interrogatorio_complementar || {}
  const hf    = cd.historia_fisiologica || {}
  const hp    = cd.historia_patologica || {}
  const hfam  = cd.historia_familiar || {}
  const hs    = cd.historia_social || {}
  const ef    = cd.exame_fisico || {}
  const sv    = ef.sinais_vitais || {}
  const hipot = cd.hipoteses_diagnosticas || []
  const agente = cd.caracteristicas_agente || ''
  const agenteIa = cd.agente_ia || {}
  const agenteSubsecoes = [
    ...AGENTE_SECOES.filter(([k]) => agenteIa[k]?.length),
    ...Object.keys(agenteIa).filter(k => k !== 'perfil' && !AGENTE_SECOES.some(([x]) => x === k) && agenteIa[k]?.length).map(k => [k, labelFor(k)]),
  ]
  const cls = cd.classificacao || {}
  const medicamentos = hp.medicamentos_em_uso || []

  // Interrogatório: novo formato (por sistema) vs legado (texto único)
  const icEntries = Object.entries(ic).filter(([k]) => k !== 'texto' && ic[k])
  const icTexto   = ic.texto || ''

  // Exame físico: sinais vitais separados + achados por aparelho
  const efAchados = Object.entries(ef).filter(([k, v]) => k !== 'sinais_vitais' && k !== 'texto_livre' && v)
  const efTextoLivre = ef.texto_livre || ''

  return (
    <Layout title={nome}>
      {backBtn}

      {/* ── Header card ─────────────────────────────────────────── */}
      <div className="card mb-16">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 24, fontWeight: 700, marginBottom: 10 }}>{nome}</h1>
            <div className="flex-row" style={{ flexWrap: 'wrap', gap: 6 }}>
              {areaLabel && <span className="badge badge-blue">{areaLabel}</span>}
              {patient.complexidade && (
                <span className={`badge ${COMPLEXITY_BADGE[compKey] || 'badge-gray'}`}>
                  Complexidade {patient.complexidade}
                </span>
              )}
              {patient.idade && <span className="badge badge-gray">{patient.idade} anos</span>}
              {sexoLabel && <span className="badge badge-gray">{sexoLabel}</span>}
              {patient.case_number && <span className="badge badge-purple">Caso #{patient.case_number}</span>}
              {patient.eixo_b && <span className="badge badge-gray">{EIXO_B_LABELS[patient.eixo_b] || patient.eixo_b}</span>}
              {cls.condicao_social && <span className="badge badge-gray">Condição social {NIVEL[cls.condicao_social] || cls.condicao_social}</span>}
            </div>
          </div>
          {user?.role === 'admin' && (
            <button className="btn btn-danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Excluindo...' : 'Excluir paciente'}
            </button>
          )}
        </div>

        {(patient.queixa_principal || cd.queixa_principal_texto) && (
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--text-muted)', marginBottom: 6 }}>
              Queixa principal
            </div>
            <p style={{ margin: 0, fontSize: 14.5, color: 'var(--text)', lineHeight: 1.65, fontStyle: 'italic' }}>
              "{patient.queixa_principal || cd.queixa_principal_texto}"
            </p>
          </div>
        )}

        {patient.diagnostico_principal && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--text-muted)', marginBottom: 4 }}>
              Diagnóstico principal
            </div>
            <p style={{ margin: 0, fontSize: 14, color: 'var(--text)' }}>{patient.diagnostico_principal}</p>
          </div>
        )}
      </div>

      {/* ── Two-column detail ───────────────────────────────────── */}
      <div className="grid-2" style={{ alignItems: 'start' }}>

        {/* LEFT: Identificação + HDA + Social */}
        <div>
          {cd.contexto_aluno && (
            <div className="card mb-16">
              <SectionHeader title="Contexto para o aluno" />
              <TextBlock text={cd.contexto_aluno} />
            </div>
          )}

          <div className="card mb-16">
            <SectionHeader title="Identificação" />
            <dl>
              <Field label="Nome"         value={nome} />
              <Field label="Idade"        value={patient.idade ? `${patient.idade} anos` : null} />
              <Field label="Sexo"         value={sexoLabel} />
              {IDENTIFICACAO_CAMPOS.map(([k, label]) => <Field key={k} label={label} value={ident[k]} />)}
            </dl>
          </div>

          {(cls.eixo_c || cls.letramento || cls.condicao_social || cls.perfil_sociodemografico || cls.nuance_eixo_b) && (
            <div className="card mb-16">
              <SectionHeader title="Classificação do caso" />
              <dl>
                <Field label="Perfil sociodemográfico (Eixo C)" value={EIXO_C_LABELS[cls.eixo_c] || cls.eixo_c} />
                <Field label="Letramento"      value={NIVEL[cls.letramento] || cls.letramento} />
                <Field label="Condição social" value={NIVEL[cls.condicao_social] || cls.condicao_social} />
                <Field label="Descrição do perfil" value={cls.perfil_sociodemografico} />
                <Field label="Nuance da comunicação (Eixo B)" value={cls.nuance_eixo_b} />
              </dl>
            </div>
          )}

          {hda && (
            <div className="card mb-16">
              <SectionHeader title="História da Doença Atual" />
              <TextBlock text={hda} />
            </div>
          )}

          {(agente || agenteIa.perfil) && (
            <div className="card mb-16">
              <SectionHeader title="Características do Agente de IA" />
              <div className="text-muted" style={{ fontSize: 11.5, marginBottom: 8 }}>Uso interno — não é mostrado ao aluno.</div>
              {agenteSubsecoes.length > 0 || agenteIa.perfil ? (
                <>
                  <TextBlock text={agenteIa.perfil} />
                  {agenteSubsecoes.map(([k, label]) => (
                    <div key={k} style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
                      <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7, fontSize: 13.5 }}>
                        {agenteIa[k].map((item, i) => <li key={i}>{item}</li>)}
                      </ul>
                    </div>
                  ))}
                </>
              ) : <TextBlock text={agente} />}
            </div>
          )}

          {/* História social */}
          {(hs.tabagismo || hs.etilismo || hs.texto_livre) && (
            <div className="card mb-16">
              <SectionHeader title="Hábitos de Vida" />
              <dl>
                <Field label="Tabagismo" value={hs.tabagismo} />
                <Field label="Etilismo"  value={hs.etilismo} />
              </dl>
              {hs.texto_livre && <TextBlock text={hs.texto_livre} />}
            </div>
          )}
        </div>

        {/* RIGHT: Diagnósticos + Exame + Histórias */}
        <div>
          {/* Hipóteses diagnósticas */}
          {hipot.length > 0 && (
            <div className="card mb-16">
              <SectionHeader title="Hipóteses Diagnósticas" />
              <ol style={{ margin: '8px 0 0', paddingLeft: 20, lineHeight: 1.9 }}>
                {hipot.map((h, i) => (
                  <li key={i} style={{ fontSize: 13.5, color: 'var(--text)' }}>{h}</li>
                ))}
              </ol>
            </div>
          )}

          {/* Exame físico */}
          {(Object.keys(sv).length > 0 || efAchados.length > 0 || efTextoLivre) && (
            <div className="card mb-16">
              <SectionHeader title="Exame Físico" />
              {Object.keys(sv).length > 0 && (
                <>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, marginTop: 8 }}>Sinais vitais</div>
                  <dl>
                    {Object.entries(sv).map(([k, v]) => (
                      <Field key={k} label={labelFor(k)} value={v} />
                    ))}
                  </dl>
                </>
              )}
              {efAchados.length > 0 && (
                <>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, marginTop: 12 }}>Achados por aparelho</div>
                  <dl>
                    {efAchados.map(([k, v]) => (
                      <Field key={k} label={labelFor(k)} value={typeof v === 'string' ? v : JSON.stringify(v)} />
                    ))}
                  </dl>
                </>
              )}
              {efTextoLivre && <TextBlock text={efTextoLivre} />}
            </div>
          )}

          {/* Interrogatório complementar */}
          {(icEntries.length > 0 || icTexto) && (
            <div className="card mb-16">
              <SectionHeader title="Interrogatório Complementar" />
              {icEntries.length > 0 ? (
                <dl>
                  {icEntries.map(([k, v]) => (
                    <Field key={k} label={labelFor(k)} value={v} />
                  ))}
                </dl>
              ) : (
                <TextBlock text={icTexto} />
              )}
            </div>
          )}

          {/* História fisiológica */}
          {hf.texto_livre && (
            <div className="card mb-16">
              <SectionHeader title="Antecedentes Fisiológicos" />
              <TextBlock text={hf.texto_livre} />
            </div>
          )}

          {/* História patológica */}
          {(hp.doencas_previas?.length || hp.cirurgias?.length || hp.internacoes?.length || hp.alergias?.length || hp.texto_livre) && (
            <div className="card mb-16">
              <SectionHeader title="Antecedentes Patológicos" />
              <dl>
                <Field label="Doenças prévias"  value={hp.doencas_previas} />
                <Field label="Cirurgias"         value={hp.cirurgias} />
                <Field label="Internações"       value={hp.internacoes} />
                <Field label="Alergias"          value={hp.alergias} />
              </dl>
              {hp.texto_livre && <TextBlock text={hp.texto_livre} />}
            </div>
          )}

          {/* Medicações em uso */}
          {(medicamentos.length > 0 || hp.medicacoes_observacao) && (
            <div className="card mb-16">
              <SectionHeader title="Medicações em Uso" />
              {medicamentos.length > 0 && (
                <ul style={{ margin: '8px 0', paddingLeft: 20, lineHeight: 1.8, fontSize: 13.5 }}>
                  {medicamentos.map((m, i) => <li key={i}>{m}</li>)}
                </ul>
              )}
              {hp.medicacoes_observacao && (
                <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.65 }}>
                  <strong>Observação:</strong> {hp.medicacoes_observacao}
                </p>
              )}
            </div>
          )}

          {/* História familiar */}
          {hfam.texto_livre && (
            <div className="card mb-16">
              <SectionHeader title="Antecedentes Familiares" />
              <TextBlock text={hfam.texto_livre} />
            </div>
          )}
        </div>
      </div>

      {/* Raw JSON viewer */}
      <details style={{ marginTop: 8 }}>
        <summary style={{ cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)', padding: '8px 0', userSelect: 'none' }}>
          Dados brutos (JSON)
        </summary>
        <pre style={{
          background: 'var(--navy)', color: '#E2EAF8',
          borderRadius: 8, padding: 16, fontSize: 11.5,
          overflow: 'auto', maxHeight: 500, marginTop: 8,
          fontFamily: "'Fira Code', 'Cascadia Code', monospace",
        }}>
          {JSON.stringify(patient.case_data, null, 2)}
        </pre>
      </details>
    </Layout>
  )
}
