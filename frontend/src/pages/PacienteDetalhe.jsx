import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'

function Section({ title, children }) {
  return (
    <div style={{ background: '#fff', borderRadius: 12, padding: '20px 24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 700, color: '#1e293b' }}>{title}</h3>
      {children}
    </div>
  )
}

function Field({ label, value }) {
  if (!value) return null
  return (
    <div style={{ marginBottom: 8 }}>
      <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      <div style={{ fontSize: 14, color: '#374151', marginTop: 2 }}>{Array.isArray(value) ? value.join(', ') : value}</div>
    </div>
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
      .catch(e => setError(e.response?.data?.detail || 'Paciente não encontrado'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>Carregando...</div>
  if (error) return (
    <div style={{ padding: 48, textAlign: 'center' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
      <p style={{ color: '#ef4444' }}>{error}</p>
      <button onClick={() => navigate(-1)} style={{ color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14 }}>← Voltar</button>
    </div>
  )

  const cd = patient?.case_data || {}
  const ident = cd.identificacao || cd.identification || {}
  const ax1 = cd.eixo_i || cd.axis_i || {}
  const ax2 = cd.eixo_ii || cd.axis_ii || {}
  const ax3 = cd.eixo_iii || cd.axis_iii || {}
  const hx = cd.historico || cd.history || cd.anamnese || {}

  return (
    <div>
      <button onClick={() => navigate(-1)} style={{ color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, marginBottom: 20, padding: 0 }}>
        ← Voltar para Pacientes
      </button>

      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: '#1e293b' }}>
            {patient.nome || ident.nome || 'Paciente Virtual'}
          </h1>
          <p style={{ margin: '4px 0 0', color: '#64748b' }}>
            {patient.area_clinica && `🏥 ${patient.area_clinica}`}
            {patient.complexidade && ` · Complexidade ${patient.complexidade}`}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Section title="📋 Identificação">
          <Field label="Nome" value={patient.nome || ident.nome} />
          <Field label="Idade" value={patient.idade || ident.idade} />
          <Field label="Gênero" value={patient.genero || ident.genero || ident.sexo} />
          <Field label="Estado Civil" value={ident.estado_civil} />
          <Field label="Ocupação" value={ident.ocupacao || ident.profissao} />
          <Field label="Escolaridade" value={ident.escolaridade} />
        </Section>

        <Section title="🧠 Diagnóstico (Eixo I)">
          <Field label="Diagnóstico Principal" value={patient.diagnostico_principal || ax1.diagnostico_principal} />
          <Field label="CID-10" value={ax1.cid10 || ax1.codigo_cid} />
          <Field label="Diagnóstico Diferencial" value={ax1.diagnostico_diferencial} />
        </Section>
      </div>

      {(ax2?.transtorno_personalidade || ax2?.caracteristicas) && (
        <Section title="🔍 Transtornos de Personalidade (Eixo II)">
          <Field label="Transtorno" value={ax2.transtorno_personalidade} />
          <Field label="Características" value={ax2.caracteristicas} />
        </Section>
      )}

      {(ax3?.condicoes_medicas || ax3?.comorbidades) && (
        <Section title="🏥 Condições Médicas (Eixo III)">
          <Field label="Condições" value={ax3.condicoes_medicas || ax3.comorbidades} />
          <Field label="Medicações" value={ax3.medicacoes || ax3.medicamentos} />
        </Section>
      )}

      {Object.keys(hx).length > 0 && (
        <Section title="📖 Histórico Clínico">
          {Object.entries(hx).map(([k, v]) => (
            <Field key={k} label={k.replace(/_/g, ' ')} value={typeof v === 'string' ? v : JSON.stringify(v)} />
          ))}
        </Section>
      )}

      {cd.queixa_principal && (
        <Section title="💬 Queixa Principal">
          <p style={{ margin: 0, fontSize: 14, color: '#374151', lineHeight: 1.6 }}>{cd.queixa_principal}</p>
        </Section>
      )}

      {patient.case_data && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: 'pointer', fontSize: 14, color: '#64748b', padding: '8px 0' }}>Ver dados brutos (JSON)</summary>
          <pre style={{
            background: '#1e293b', color: '#e2e8f0', borderRadius: 8, padding: 16,
            fontSize: 12, overflow: 'auto', maxHeight: 400, marginTop: 8,
          }}>
            {JSON.stringify(patient.case_data, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}
