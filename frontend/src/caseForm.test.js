import { describe, expect, it } from 'vitest'
import { applyExtracted, buildPayload, EMPTY_FORM, patientToExtracted, validate } from './caseForm'

const HDA = 'Paciente relata dor precordial em aperto há dois meses, desencadeada por esforço moderado e aliviada com repouso.'

// Paciente como devolvido por GET /kb/patients/{id} (colunas + case_data do modelo padronizado).
const PATIENT = {
  id: 'abc',
  eixo_a: 'clinica_cirurgica', eixo_a_secundario: 'cardiovascular',
  eixo_b: 'ansioso', eixo_c: 'medio_letramento_media', complexidade: 'alta',
  nome: 'João Cardoso', idade: 55, sexo: 'M',
  queixa_principal: 'Dor no peito ao esforço', diagnostico_principal: 'Angina Estável',
  case_data: {
    contexto_aluno: 'Consultório de UBS',
    identificacao: { nome: 'João Cardoso', idade: 55, sexo: 'M', profissao: 'Pedreiro', cor: null },
    historia_doenca_atual: HDA,
    interrogatorio_complementar: { cabeca: 'Cefaleia ocasional', torax: 'Dor ao esforço' },
    historia_fisiologica: { texto_livre: 'Parto normal' },
    historia_patologica: {
      doencas_previas: ['HAS'], cirurgias: [], internacoes: [], alergias: ['Dipirona'],
      medicamentos_em_uso: ['Losartana 50mg'], texto_livre: 'HAS há 10 anos', medicacoes_observacao: 'Toma pela manhã',
    },
    historia_familiar: { texto_livre: 'Pai infartou aos 60' },
    historia_social: { tabagismo: 'Ex-tabagista', etilismo: null, texto_livre: 'Sedentário' },
    exame_fisico: {
      sinais_vitais: { pa: '150/90', fc: '82' },
      aparelho_cardiovascular: 'Bulhas normofonéticas',
      texto_livre: 'texto derivado pelo backend',
    },
    agente_ia: { perfil: 'Fala pausado', voz_postura_discurso: ['Voz baixa', 'Olha para o chão'] },
    hipoteses_diagnosticas: ['Angina Estável', 'IAM'],
    classificacao: { letramento: 'medio', condicao_social: 'media', nuance_eixo_b: 'Teme o diagnóstico' },
  },
}

describe('patientToExtracted', () => {
  const ext = patientToExtracted(PATIENT)

  it('copia colunas, incluindo a segunda área', () => {
    expect(ext).toMatchObject({
      eixo_a: 'clinica_cirurgica', eixo_a_secundario: 'cardiovascular', eixo_b: 'ansioso',
      eixo_c: 'medio_letramento_media', complexidade: 'alta', nome: 'João Cardoso', idade: 55, sexo: 'M',
    })
  })

  it('segunda área ausente vira string vazia', () => {
    expect(patientToExtracted({ ...PATIENT, eixo_a_secundario: null }).eixo_a_secundario).toBe('')
  })

  it('lê identificação, classificação e textos do case_data', () => {
    expect(ext.profissao).toBe('Pedreiro')
    expect(ext.letramento).toBe('medio')
    expect(ext.nuance_eixo_b).toBe('Teme o diagnóstico')
    expect(ext.historia_fisiologica).toBe('Parto normal')
    expect(ext.historia_familiar).toBe('Pai infartou aos 60')
    expect(ext.historia_social_texto).toBe('Sedentário')
    expect(ext.medicamentos_em_uso).toEqual(['Losartana 50mg'])
  })

  it('remove o texto_livre derivado do exame físico', () => {
    expect(ext.exame_fisico.texto_livre).toBeUndefined()
    expect(ext.exame_fisico.aparelho_cardiovascular).toBe('Bulhas normofonéticas')
  })

  it('exame físico legado (só texto_livre) vira texto único', () => {
    const legacy = { ...PATIENT, case_data: { ...PATIENT.case_data, exame_fisico: { texto_livre: 'Exame normal' } } }
    expect(patientToExtracted(legacy).exame_fisico).toBe('Exame normal')
  })

  it('tolera case_data vazio', () => {
    expect(() => applyExtracted(patientToExtracted({ nome: 'X', case_data: {} }))).not.toThrow()
  })
})

describe('edição: paciente -> formulário -> payload', () => {
  const { form, nested } = applyExtracted(patientToExtracted(PATIENT))

  it('pré-preenche o formulário e os objetos aninhados', () => {
    expect(form.nome).toBe('João Cardoso')
    expect(form.eixo_a_secundario).toBe('cardiovascular')
    expect(form.alergias).toEqual(['Dipirona'])
    expect(nested.interrogatorio.cabeca).toBe('Cefaleia ocasional')
    expect(nested.sinais).toEqual({ pa: '150/90', fc: '82' })
    expect(nested.exame.texto_livre).toBeUndefined()
    expect(nested.agente.voz_postura_discurso).toBe('Voz baixa\nOlha para o chão')
  })

  it('o formulário carregado é válido', () => {
    expect(validate(form)).toEqual({})
  })

  it('round-trip: o payload reproduz os dados do paciente', () => {
    const payload = buildPayload(form, nested)
    expect(payload).toMatchObject({
      eixo_a: 'clinica_cirurgica', eixo_a_secundario: 'cardiovascular', nome: 'João Cardoso', idade: 55,
      historia_doenca_atual: HDA, medicamentos_em_uso: ['Losartana 50mg'],
      hipoteses_diagnosticas: ['Angina Estável', 'IAM'],
    })
    expect(payload.interrogatorio_complementar).toEqual({ cabeca: 'Cefaleia ocasional', torax: 'Dor ao esforço' })
    expect(payload.exame_fisico).toEqual({
      aparelho_cardiovascular: 'Bulhas normofonéticas', sinais_vitais: { pa: '150/90', fc: '82' },
    })
    expect(payload.agente_ia).toEqual({ perfil: 'Fala pausado', voz_postura_discurso: ['Voz baixa', 'Olha para o chão'] })
  })

  it('campo editado aparece no payload', () => {
    const payload = buildPayload({ ...form, nome: 'João Editado', idade: '60' }, nested)
    expect(payload.nome).toBe('João Editado')
    expect(payload.idade).toBe(60)
  })

  it('limpar a segunda área não a envia', () => {
    expect(buildPayload({ ...form, eixo_a_secundario: '' }, nested).eixo_a_secundario).toBeUndefined()
  })
})

describe('validate', () => {
  it('formulário vazio tem os campos obrigatórios em erro', () => {
    expect(Object.keys(validate(EMPTY_FORM))).toEqual(
      expect.arrayContaining(['eixo_a', 'nome', 'idade', 'sexo', 'queixa_principal', 'diagnostico_principal', 'historia_doenca_atual']),
    )
  })

  it('segunda área igual à principal é rejeitada', () => {
    const { form } = applyExtracted(patientToExtracted(PATIENT))
    expect(validate({ ...form, eixo_a_secundario: form.eixo_a }).eixo_a_secundario).toBeDefined()
  })
})
