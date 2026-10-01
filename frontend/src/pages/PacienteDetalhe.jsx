import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import client from '../api/client'

const COMPLEXITY_BADGE = { baixa: 'badge-green', media: 'badge-amber', alta: 'badge-red' }

function Field({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  const display = Array.isArray(value) ? value.join(', ') : typeof value === 'object' ? JSON.stringify(value) : String(value)
  if (!display) return null
  return (
    <div className="detail-pair">
      <dt>{label}</dt>
      <dd>{display}</dd>
    </div>
  )
}

function Section({ title, children }) {
  const hasContent = Array.isArray(children)
    ? children.some(c => c !== null && c !== undefined && c !== false)
    : children !== null && children !== undefined && children !== false
  if (!hasContent) return null
  return (
    <>
      <div className="detail-section">{title}</div>
      <dl>{children}</dl>
    </>
  )
}

export default function PacienteDetalhe() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [patient, setPatient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    client.get(`/kb/patients/${id}`)
      .then(r => setPatient(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Paciente nao encontrado'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return (
    <Layout>
      <div className="loading-wrap"><div className="spinner"/><span>Carregando paciente...</span></div>
    </Layout>
  )

  if (error) return (
    <Layout>
      <div style={{ padding: '16px 0' }}>
        <button className="btn btn-outline mb-16" onClick={() => navigate(-1)} style={{ gap: 6 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          Voltar
        </button>
        <div className="alert alert-error">{error}</div>
      </div>
    </Layout>
  )

  const cd  = patient?.case_data || {}
  const ident = cd.identificacao   || cd.identification || {}
  const ax1   = cd.eixo_i          || cd.axis_i         || {}
  const ax2   = cd.eixo_ii         || cd.axis_ii        || {}
  const ax3   = cd.eixo_iii        || cd.axis_iii       || {}
  const ax4   = cd.eixo_iv         || cd.axis_iv        || {}
  const ax5   = cd.eixo_v          || cd.axis_v         || {}
  const hx    = cd.historico        || cd.history        || cd.anamnese || {}
  const sx    = cd.sinais_vitais    || cd.vital_signs    || cd.sinais   || {}
  const mh    = cd.exame_mental     || cd.mental_status  || {}
  const rx    = cd.tratamento       || cd.treatment      || {}

  const nome = patient.nome || ident.nome || ident.name || 'Paciente Virtual'
  const compKey = (patient.complexidade || '').toLowerCase()

  return (
    <Layout>
      {/* Back */}
      <button className="btn btn-outline mb-24" onClick={() => navigate(-1)} style={{ gap: 6 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>
        Voltar para Pacientes
      </button>

      {/* Header */}
      <div className="card mb-16">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontFamily: "'DM Sans',sans-serif", fontSize: 26, fontWeight: 700, marginBottom: 8 }}>{nome}</h1>
            <div className="flex-row" style={{ flexWrap: 'wrap', gap: 6 }}>
              {patient.area_clinica && <span className="badge badge-blue">{patient.area_clinica}</span>}
              {patient.complexidade && (
                <span className={`badge ${COMPLEXITY_BADGE[compKey] || 'badge-gray'}`}>
                  Complexidade {patient.complexidade}
                </span>
              )}
              {(patient.idade || ident.idade) && (
                <span className="badge badge-gray">{patient.idade || ident.idade} anos</span>
              )}
              {(patient.genero || ident.genero || ident.sexo) && (
                <span className="badge badge-gray">{patient.genero || ident.genero || ident.sexo}</span>
              )}
            </div>
          </div>
        </div>

        {cd.queixa_principal && (
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--text-muted)', marginBottom: 6 }}>Queixa principal</div>
            <p style={{ margin: 0, fontSize: 14, color: 'var(--text)', lineHeight: 1.65 }}>{cd.queixa_principal}</p>
          </div>
        )}
      </div>

      {/* Details */}
      <div className="grid-2" style={{ alignItems: 'start' }}>
        {/* Left column */}
        <div className="card">
          <Section title="Identificacao">
            <Field label="Nome" value={patient.nome || ident.nome || ident.name} />
            <Field label="Idade" value={patient.idade || ident.idade || ident.age} />
            <Field label="Genero" value={patient.genero || ident.genero || ident.sexo || ident.gender} />
            <Field label="Estado civil" value={ident.estado_civil || ident.marital_status} />
            <Field label="Ocupacao" value={ident.ocupacao || ident.profissao || ident.occupation} />
            <Field label="Escolaridade" value={ident.escolaridade || ident.education} />
            <Field label="Naturalidade" value={ident.naturalidade || ident.cidade || ident.city} />
            <Field label="Encaminhado por" value={ident.encaminhado_por || ident.referral} />
          </Section>

          {Object.keys(hx).length > 0 && (
            <Section title="Historico clinico">
              {Object.entries(hx).map(([k, v]) => (
                <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' ? v : JSON.stringify(v)} />
              ))}
            </Section>
          )}

          {Object.keys(sx).length > 0 && (
            <Section title="Sinais vitais">
              {Object.entries(sx).map(([k, v]) => (
                <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' || typeof v === 'number' ? v : JSON.stringify(v)} />
              ))}
            </Section>
          )}
        </div>

        {/* Right column */}
        <div>
          <div className="card mb-16">
            <Section title="Diagnostico — Eixo I">
              <Field label="Diagnostico principal" value={patient.diagnostico_principal || ax1.diagnostico_principal || ax1.main_diagnosis} />
              <Field label="CID-10" value={ax1.cid10 || ax1.codigo_cid || ax1.cid || ax1.icd10} />
              <Field label="Diagnostico diferencial" value={ax1.diagnostico_diferencial || ax1.differential_diagnosis} />
              <Field label="Especificador" value={ax1.especificador || ax1.specifier} />
              <Field label="Curso" value={ax1.curso || ax1.course} />
            </Section>

            {(ax2.transtorno_personalidade || ax2.caracteristicas || ax2.personality_disorder || Object.keys(ax2).length > 0) && (
              <Section title="Transtorno de personalidade — Eixo II">
                <Field label="Transtorno" value={ax2.transtorno_personalidade || ax2.personality_disorder} />
                <Field label="Caracteristicas" value={ax2.caracteristicas || ax2.characteristics} />
                <Field label="Observacoes" value={ax2.observacoes || ax2.notes} />
              </Section>
            )}

            {(ax3.condicoes_medicas || ax3.comorbidades || ax3.medical_conditions || Object.keys(ax3).length > 0) && (
              <Section title="Condicoes medicas — Eixo III">
                <Field label="Condicoes" value={ax3.condicoes_medicas || ax3.comorbidades || ax3.medical_conditions} />
                <Field label="Medicacoes" value={ax3.medicacoes || ax3.medicamentos || ax3.medications} />
              </Section>
            )}

            {Object.keys(ax4).length > 0 && (
              <Section title="Fatores psicossociais — Eixo IV">
                {Object.entries(ax4).map(([k, v]) => (
                  <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' ? v : JSON.stringify(v)} />
                ))}
              </Section>
            )}

            {Object.keys(ax5).length > 0 && (
              <Section title="Avaliacao global — Eixo V">
                {Object.entries(ax5).map(([k, v]) => (
                  <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' || typeof v === 'number' ? v : JSON.stringify(v)} />
                ))}
              </Section>
            )}
          </div>

          {Object.keys(mh).length > 0 && (
            <div className="card mb-16">
              <Section title="Exame do estado mental">
                {Object.entries(mh).map(([k, v]) => (
                  <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' ? v : JSON.stringify(v)} />
                ))}
              </Section>
            </div>
          )}

          {Object.keys(rx).length > 0 && (
            <div className="card">
              <Section title="Tratamento">
                {Object.entries(rx).map(([k, v]) => (
                  <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' ? v : JSON.stringify(v)} />
                ))}
              </Section>
            </div>
          )}
        </div>
      </div>

      {/* Raw JSON */}
      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: 'pointer', fontSize: 13, color: 'var(--text-muted)', padding: '8px 0', userSelect: 'none' }}>
          Dados brutos (JSON)
        </summary>
        <pre style={{
          background: 'var(--navy)', color: '#E2EAF8',
          borderRadius: 8, padding: 16, fontSize: 12,
          overflow: 'auto', maxHeight: 400, marginTop: 8,
          fontFamily: "'Fira Code', monospace",
        }}>
          {JSON.stringify(patient.case_data, null, 2)}
        </pre>
      </details>
    </Layout>
  )
}
