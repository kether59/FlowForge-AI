import clsx from 'clsx'
import { CheckCircle2, FlaskConical, RefreshCw, Trash2, Upload, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../lib/api'
import type { FlowNodeData } from '../lib/types'
import { useFlowStore } from '../store/useFlowStore'
import { Field, JsonView, Select, Slider, TextArea, TextInput, Toggle } from './ui'

const DEFAULT_SYSTEM_PROMPT =
  "Tu es un assistant d'entreprise précis et concis. Réponds en français. Si des extraits documentaires sont fournis, appuie-toi uniquement sur eux et cite la source entre crochets."

export function ConfigPanel() {
  const { nodes, selectedNodeId, updateConfig, updateLabel, deleteNode, providers, specByType } =
    useFlowStore()
  const node = nodes.find((n) => n.id === selectedNodeId)

  if (!node) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
        <p className="text-sm font-medium text-slate-300">Aucun bloc sélectionné</p>
        <p className="text-xs leading-relaxed text-slate-500">
          Cliquez sur un bloc du canvas pour éditer sa configuration, ou glissez un nouveau bloc
          depuis la palette.
        </p>
      </div>
    )
  }

  const data = node.data
  const spec = specByType[data.nodeType]
  const set = (patch: Record<string, any>) => updateConfig(node.id, patch)

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: spec?.color }} />
          <span className="text-[11px] uppercase tracking-wider text-slate-500">
            {spec?.label ?? data.nodeType}
          </span>
          <span className="ml-auto font-mono text-[10px] text-slate-600">{node.id}</span>
        </div>
        <input
          className="mt-2 w-full rounded-md border border-transparent bg-transparent px-0 py-1 text-base font-semibold text-slate-100 outline-none focus:border-slate-700 focus:px-2"
          value={data.label}
          onChange={(e) => updateLabel(node.id, e.target.value)}
        />
        <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{spec?.description}</p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {data.nodeType === 'llm' && <LLMConfig config={data.config} set={set} providers={providers} />}
        {data.nodeType === 'source' && <SourceConfig config={data.config} set={set} />}
        {data.nodeType === 'vectorStore' && <VectorStoreConfig config={data.config} set={set} />}
        {data.nodeType === 'condition' && <ConditionConfig config={data.config} set={set} />}
        {data.nodeType === 'logicGate' && <LogicGateConfig config={data.config} set={set} />}
        {data.nodeType === 'merge' && <MergeConfig config={data.config} set={set} />}
        {data.nodeType === 'template' && <TemplateConfig config={data.config} set={set} />}
        {data.nodeType === 'code' && <CodeConfig config={data.config} set={set} />}
        {data.nodeType === 'input' && <InputConfig config={data.config} set={set} />}
        {data.nodeType === 'output' && <OutputConfig config={data.config} set={set} />}

        <div className="mt-6 rounded-lg border border-slate-800 bg-slate-900/40 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Payloads configurés
          </p>
          <JsonView value={data.config} />
        </div>
      </div>

      <div className="border-t border-slate-800 p-3">
        <button className="btn-danger w-full justify-center" onClick={() => deleteNode(node.id)}>
          <Trash2 size={14} /> Supprimer le bloc
        </button>
      </div>
    </div>
  )
}

type CfgProps = { config: Record<string, any>; set: (patch: Record<string, any>) => void }

function LLMConfig({ config, set, providers }: CfgProps & { providers: ReturnType<typeof useFlowStore.getState>['providers'] }) {
  const [test, setTest] = useState<{ ok: boolean; text?: string; error?: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const providerList = providers?.providers ?? {}
  const current = providerList[config.provider] ?? providerList['mock']
  const models = current?.models ?? [config.model].filter(Boolean)

  const runTest = async () => {
    setTesting(true)
    try {
      setTest(await api.testProvider(config.provider ?? 'mock', config.model ?? models[0]))
    } catch (err: any) {
      setTest({ ok: false, error: err?.message })
    } finally {
      setTesting(false)
    }
  }

  return (
    <>
      <Field label="Provider">
        <Select
          value={config.provider ?? 'mock'}
          onChange={(provider) =>
            set({ provider, model: providerList[provider]?.models?.[0] ?? config.model })
          }
          options={Object.entries(providerList).map(([key, info]) => ({
            value: key,
            label: `${info.label}${info.configured ? '' : ' · clé manquante'}`,
          }))}
        />
      </Field>
      <Field label="Modèle">
        <Select
          value={config.model ?? models[0] ?? ''}
          onChange={(model) => set({ model })}
          options={models.map((m) => ({ value: m, label: m }))}
        />
      </Field>
      {current && !current.configured && (
        <p className="mb-3 rounded-lg border border-amber-800/60 bg-amber-950/40 px-2.5 py-2 text-[11px] leading-relaxed text-amber-300">
          Ce provider n'a pas de clé API configurée. Le nœud échouera à l'exécution : renseignez la
          variable d'environnement correspondante ou utilisez « Mock (hors ligne) ».
        </p>
      )}

      <Field
        label="System Prompt"
        hint={
          <button
            className="text-indigo-400 hover:text-indigo-300"
            onClick={() => set({ systemPrompt: DEFAULT_SYSTEM_PROMPT })}
          >
            Réinitialiser le prompt par défaut
          </button>
        }
      >
        <TextArea
          value={config.systemPrompt ?? ''}
          onChange={(systemPrompt) => set({ systemPrompt })}
          rows={6}
        />
      </Field>

      <Field label="Température">
        <Slider
          value={Number(config.temperature ?? 0.7)}
          onChange={(temperature) => set({ temperature })}
          min={0}
          max={2}
          step={0.05}
        />
      </Field>

      <Field label="Max tokens">
        <TextInput
          type="number"
          value={config.maxTokens ?? 512}
          onChange={(v) => set({ maxTokens: Number(v) || 1 })}
        />
      </Field>

      <Toggle
        label="Mémoire conversationnelle"
        checked={Boolean(config.memoryEnabled)}
        onChange={(memoryEnabled) => set({ memoryEnabled })}
      />
      {config.memoryEnabled && (
        <Field label="Fenêtre de mémoire (messages)">
          <Slider
            value={Number(config.memoryWindow ?? 6)}
            onChange={(memoryWindow) => set({ memoryWindow })}
            min={0}
            max={20}
            step={1}
          />
        </Field>
      )}

      <button className="btn-ghost w-full justify-center" onClick={runTest} disabled={testing}>
        <FlaskConical size={14} /> {testing ? 'Test en cours…' : 'Tester le provider'}
      </button>
      {test && (
        <div
          className={clsx(
            'mt-3 rounded-lg border px-2.5 py-2 text-[11px] leading-relaxed',
            test.ok
              ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-300'
              : 'border-rose-800/60 bg-rose-950/40 text-rose-300',
          )}
        >
          {test.ok ? test.text : test.error}
        </div>
      )}
    </>
  )
}

function SourceConfig({ config, set }: CfgProps) {
  const [uploads, setUploads] = useState<{ id: string; name: string; size: number }[]>([])
  const [importResult, setImportResult] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const kind = config.kind ?? 'inline'

  useEffect(() => {
    if (kind === 'upload') api.uploads().then(setUploads).catch(() => setUploads([]))
  }, [kind])

  const toggleFile = (fileId: string) => {
    const current: string[] = config.fileIds ?? []
    set({
      fileIds: current.includes(fileId) ? current.filter((id) => id !== fileId) : [...current, fileId],
    })
  }

  const onUpload = async (file?: File) => {
    if (!file) return
    setBusy(true)
    try {
      const res = await api.uploadSource(file)
      setUploads(await api.uploads())
      set({ fileIds: [...(config.fileIds ?? []), res.document.id] })
      setImportResult(`« ${res.document.name} » : ${res.chars} caractères extraits`)
    } catch (err: any) {
      setImportResult(`Erreur : ${err?.message}`)
    } finally {
      setBusy(false)
    }
  }

  const testImport = async () => {
    setBusy(true)
    setImportResult(null)
    try {
      const res =
        kind === 'drive'
          ? await api.importDrive({
              folderId: config.driveFolderId || null,
              limit: Number(config.limit ?? 10),
            })
          : await api.importConfluence({
              spaceKey: config.confluenceSpaceKey || null,
              pageId: config.confluencePageId || null,
              limit: Number(config.limit ?? 10),
            })
      setImportResult(
        `${res.documents.length} document(s) — mode « ${res.mode?.mode ?? '?'} »` +
          (res.mode?.reason ? ` (${res.mode.reason})` : '') +
          (res.mode?.error ? ` (${res.mode.error})` : ''),
      )
    } catch (err: any) {
      setImportResult(`Erreur : ${err?.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Field label="Type de source">
        <Select
          value={kind}
          onChange={(k) => set({ kind: k })}
          options={[
            { value: 'inline', label: 'Texte inline' },
            { value: 'upload', label: 'Fichiers uploadés (PDF / TXT)' },
            { value: 'drive', label: 'Google Drive' },
            { value: 'confluence', label: 'Confluence Atlassian' },
          ]}
        />
      </Field>

      {kind === 'inline' && (
        <Field label="Texte du document" hint="Utile pour tester rapidement une chaîne RAG.">
          <TextArea value={config.text ?? ''} onChange={(text) => set({ text })} rows={10} />
        </Field>
      )}

      {kind === 'upload' && (
        <>
          <label className="btn-ghost mb-3 w-full cursor-pointer justify-center">
            <Upload size={14} /> {busy ? 'Import…' : 'Uploader un document'}
            <input
              type="file"
              className="hidden"
              accept=".pdf,.txt,.md,.csv,.json"
              onChange={(e) => onUpload(e.target.files?.[0])}
            />
          </label>
          <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
            Le texte est extrait à l’import. Pour le RAG, reliez cette source à un Vector Store en mode
            index, puis réutilisez le même identifiant de store en mode recherche.
          </p>
          <div className="mb-3 space-y-1">
            {uploads.length === 0 && (
              <p className="text-[11px] text-slate-500">Aucun fichier importé pour le moment.</p>
            )}
            {uploads.map((file) => (
              <label
                key={file.id}
                className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-800 bg-slate-900/60 px-2 py-1.5 text-[11px] text-slate-300 hover:border-slate-700"
              >
                <input
                  type="checkbox"
                  className="accent-indigo-500"
                  checked={(config.fileIds ?? []).includes(file.id)}
                  onChange={() => toggleFile(file.id)}
                />
                <span className="flex-1 truncate">{file.name}</span>
                <span className="text-slate-600">{Math.round(file.size / 1024)} Ko</span>
              </label>
            ))}
          </div>
        </>
      )}

      {kind === 'drive' && (
        <>
          <Field
            label="ID du dossier Drive"
            hint="Laissez vide pour lister la racine. Nécessite GOOGLE_DRIVE_CREDENTIALS ; sinon un jeu de documents de démo est utilisé."
          >
            <TextInput
              value={config.driveFolderId ?? ''}
              onChange={(driveFolderId) => set({ driveFolderId })}
              placeholder="1AbC…"
            />
          </Field>
          <Field label="Nombre max de fichiers">
            <TextInput
              type="number"
              value={config.limit ?? 10}
              onChange={(v) => set({ limit: Number(v) || 1 })}
            />
          </Field>
          <button className="btn-ghost w-full justify-center" onClick={testImport} disabled={busy}>
            <FlaskConical size={14} /> Tester l'import Drive
          </button>
        </>
      )}

      {kind === 'confluence' && (
        <>
          <Field label="Clé d'espace (space key)">
            <TextInput
              value={config.confluenceSpaceKey ?? ''}
              onChange={(confluenceSpaceKey) => set({ confluenceSpaceKey })}
              placeholder="DEMO"
            />
          </Field>
          <Field label="ID de page (optionnel)">
            <TextInput
              value={config.confluencePageId ?? ''}
              onChange={(confluencePageId) => set({ confluencePageId })}
              placeholder="123456"
            />
          </Field>
          <Field label="Nombre max de pages">
            <TextInput
              type="number"
              value={config.limit ?? 10}
              onChange={(v) => set({ limit: Number(v) || 1 })}
            />
          </Field>
          <button className="btn-ghost w-full justify-center" onClick={testImport} disabled={busy}>
            <FlaskConical size={14} /> Tester l'import Confluence
          </button>
        </>
      )}

      {importResult && (
        <p className="mt-3 rounded-lg border border-slate-700 bg-slate-900/70 px-2.5 py-2 text-[11px] leading-relaxed text-slate-300">
          {importResult}
        </p>
      )}
    </>
  )
}

function VectorStoreConfig({ config, set }: CfgProps) {
  const [stores, setStores] = useState<{ storeId: string; vectors: number }[]>([])
  const [info, setInfo] = useState<string | null>(null)

  useEffect(() => {
    api.vectorStores().then(setStores).catch(() => setStores([]))
  }, [])

  const inspect = async () => {
    try {
      const res = await api.queryVectorStore(config.storeId ?? 'default', config.query || 'test')
      setInfo(`${res.vectors} vecteur(s) dans « ${config.storeId} »`)
    } catch (err: any) {
      setInfo(`Erreur : ${err?.message}`)
    }
  }

  const clear = async () => {
    await api.clearVectorStore(config.storeId ?? 'default').catch(() => null)
    setInfo(`Store « ${config.storeId} » vidé`)
    setStores(await api.vectorStores().catch(() => []))
  }

  return (
    <>
      <Field label="Opération">
        <Select
          value={config.operation ?? 'index'}
          onChange={(operation) => set({ operation })}
          options={[
            { value: 'index', label: 'Indexer les documents (chunking + embeddings)' },
            { value: 'query', label: 'Rechercher (retrieval top-k)' },
          ]}
        />
      </Field>
      <Field label="Identifiant du store" hint={stores.map((s) => `${s.storeId} (${s.vectors})`).join(' · ') || 'Aucun store existant'}>
        <TextInput value={config.storeId ?? 'default'} onChange={(storeId) => set({ storeId })} />
      </Field>

      {config.operation === 'index' ? (
        <>
          <Field label="Taille des chunks (caractères)">
            <Slider
              value={Number(config.chunkSize ?? 800)}
              onChange={(chunkSize) => set({ chunkSize })}
              min={200}
              max={2000}
              step={50}
            />
          </Field>
          <Field label="Recouvrement (overlap)">
            <Slider
              value={Number(config.chunkOverlap ?? 120)}
              onChange={(chunkOverlap) => set({ chunkOverlap })}
              min={0}
              max={500}
              step={10}
            />
          </Field>
          <Toggle label="Vider le store avant indexation" checked={Boolean(config.reset)} onChange={(reset) => set({ reset })} />
        </>
      ) : (
        <>
          <Field label="Top-K" hint="Nombre de passages injectés dans le contexte du LLM.">
            <Slider value={Number(config.topK ?? 4)} onChange={(topK) => set({ topK })} min={1} max={12} step={1} />
          </Field>
          <Field label="Requête (optionnel)" hint="Si vide, le prompt entrant est utilisé comme requête.">
            <TextInput value={config.query ?? ''} onChange={(query) => set({ query })} placeholder="Laisser vide" />
          </Field>
        </>
      )}

      <div className="flex gap-2">
        <button className="btn-ghost flex-1 justify-center" onClick={inspect} disabled={!config.storeId}>
          <RefreshCw size={13} /> Inspecter
        </button>
        <button className="btn-ghost flex-1 justify-center" onClick={clear} disabled={!config.storeId}>
          <Trash2 size={13} /> Vider
        </button>
      </div>
      {info && <p className="mt-2 text-[11px] text-slate-400">{info}</p>}
    </>
  )
}

function ConditionConfig({ config, set }: CfgProps) {
  const mode = config.mode ?? 'expression'
  return (
    <>
      <Field label="Mode d'évaluation">
        <Select
          value={mode}
          onChange={(m) => set({ mode: m })}
          options={[
            { value: 'expression', label: 'Expression Python' },
            { value: 'contains', label: 'Contient un des mots-clés' },
            { value: 'regex', label: 'Expression régulière' },
          ]}
        />
      </Field>
      {mode === 'expression' && (
        <Field label="Expression" hint='Variables disponibles : text, payload, len, float, int, str, bool. Ex. len(text) > 200 and "erreur" in text.lower()'>
          <TextArea mono value={config.expression ?? ''} onChange={(expression) => set({ expression })} rows={3} />
        </Field>
      )}
      {mode === 'contains' && (
        <Field label="Mots-clés séparés par des virgules">
          <TextInput value={config.keywords ?? ''} onChange={(keywords) => set({ keywords })} />
        </Field>
      )}
      {mode === 'regex' && (
        <Field label="Pattern">
          <TextInput mono value={config.pattern ?? ''} onChange={(pattern) => set({ pattern })} />
        </Field>
      )}
      <Toggle
        label="Sensible à la casse"
        checked={Boolean(config.caseSensitive)}
        onChange={(caseSensitive) => set({ caseSensitive })}
      />
      <p className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2 text-[11px] leading-relaxed text-slate-400">
        Les sorties <span className="text-emerald-400">True</span> et{' '}
        <span className="text-rose-400">False</span> alimentent deux branches distinctes. Les blocs
        de la branche non empruntée sont marqués <em>skipped</em>.
      </p>
    </>
  )
}

function LogicGateConfig({ config, set }: CfgProps) {
  return (
    <>
      <Field label="Porte logique" hint="A, B, C correspondent aux handles input1, input2, input3.">
        <Select
          value={config.gate ?? 'and'}
          onChange={(gate) => set({ gate })}
          options={[
            { value: 'and', label: 'AND — toutes les branches actives' },
            { value: 'or', label: 'OR — au moins une branche' },
            { value: 'xor', label: 'XOR — exactement une branche' },
            { value: 'nand', label: 'NAND — pas toutes les branches' },
          ]}
        />
      </Field>
      <p className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2 text-[11px] leading-relaxed text-slate-400">
        Un handle non câblé est ignoré. Si la condition n'est pas remplie, le bloc est marqué{' '}
        <em>skipped</em> et le flux s'arrête sur cette branche.
      </p>
    </>
  )
}

function MergeConfig({ config, set }: CfgProps) {
  return (
    <>
      <Field label="Mode de fusion">
        <Select
          value={config.mode ?? 'concat'}
          onChange={(mode) => set({ mode })}
          options={[
            { value: 'concat', label: 'Concaténer en un texte' },
            { value: 'array', label: 'Tableau d\'éléments' },
            { value: 'object', label: 'Objet { handle: valeur }' },
            { value: 'first', label: 'Première entrée disponible' },
          ]}
        />
      </Field>
      {config.mode === 'concat' && (
        <Field label="Séparateur">
          <TextInput mono value={config.separator ?? '\n\n'} onChange={(separator) => set({ separator })} />
        </Field>
      )}
    </>
  )
}

function TemplateConfig({ config, set }: CfgProps) {
  return (
    <Field
      label="Template"
      hint="Variables : {{text}}, {{input}}, {{context}}, {{prompt}} — ou toute clé du payload entrant."
    >
      <TextArea mono value={config.template ?? ''} onChange={(template) => set({ template })} rows={8} />
    </Field>
  )
}

function CodeConfig({ config, set }: CfgProps) {
  return (
    <>
      <Field
        label="Script Python"
        hint="Variables injectées : payload (entrée du bloc), context (runId, workflowId…). Assignez result, ou définissez run(payload, context). Exécution dans un sous-processus isolé avec timeout."
      >
        <TextArea mono value={config.code ?? ''} onChange={(code) => set({ code })} rows={16} />
      </Field>
      <Field label="Timeout (secondes)">
        <TextInput
          type="number"
          value={config.timeout ?? 10}
          onChange={(v) => set({ timeout: Number(v) || 5 })}
        />
      </Field>
    </>
  )
}

function InputConfig({ config, set }: CfgProps) {
  return (
    <>
      <Field label="Champ du payload attendu" hint="Le Chat envoie { prompt: '…' }.">
        <TextInput value={config.field ?? 'prompt'} onChange={(field) => set({ field })} />
      </Field>
      <Field label="Placeholder du chat">
        <TextInput value={config.placeholder ?? ''} onChange={(placeholder) => set({ placeholder })} />
      </Field>
    </>
  )
}

function OutputConfig({ config, set }: CfgProps) {
  return (
    <>
      <Field label="Format de sortie">
        <Select
          value={config.format ?? 'text'}
          onChange={(format) => set({ format })}
          options={[
            { value: 'text', label: 'Texte' },
            { value: 'json', label: 'JSON (payload brut)' },
          ]}
        />
      </Field>
      <Field label="Titre affiché">
        <TextInput value={config.title ?? ''} onChange={(title) => set({ title })} />
      </Field>
      <p className="flex items-start gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-2 text-[11px] text-slate-400">
        <CheckCircle2 size={12} className="mt-0.5 text-emerald-500" />
        La valeur reçue devient la réponse finale renvoyée au chat.
        <XCircle size={12} className="hidden" />
      </p>
    </>
  )
}
