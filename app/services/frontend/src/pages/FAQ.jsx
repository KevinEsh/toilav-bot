import { useState, useEffect } from "react"
import axios from "axios"
import { Plus, Pencil, Trash2, Eye, Search, MessageCircle } from "lucide-react"
import TopBar from "@/components/layout/TopBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"

const API = "http://localhost:8000"

const CATEGORIES = [
  { value: "orders",     label: "Pedidos",       icon: "📦" },
  { value: "shipping",   label: "Envíos",        icon: "🚚" },
  { value: "payments",   label: "Pagos",         icon: "💳" },
  { value: "returns",    label: "Devoluciones",  icon: "↩️" },
  { value: "products",   label: "Productos",     icon: "🛍️" },
  { value: "account",    label: "Cuenta",        icon: "👤" },
  { value: "promotions", label: "Promociones",   icon: "🎉" },
  { value: "general",    label: "General",       icon: "💬" },
  { value: "other",      label: "Otro",          icon: "❓" },
]

const CATEGORY_MAP = Object.fromEntries(CATEGORIES.map((c) => [c.value, c]))

function getCategoryMeta(raw) {
  return CATEGORY_MAP[raw?.toLowerCase()] || { value: raw, label: raw || "General", icon: "💬" }
}

const emptyForm = {
  faq_category: "general",
  faq_question: "",
  faq_answer: "",
  faq_is_active: true,
  faq_display_order: 0,
}

function groupByCategory(faqs) {
  const groups = {}
  for (const f of faqs) {
    const cat = f.faq_category?.toLowerCase() || "general"
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(f)
  }
  return groups
}

function FaqCardSkeleton() {
  return (
    <div className="px-5 py-4 flex items-start gap-3">
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-16" />
      </div>
      <Skeleton className="h-5 w-10 rounded-full" />
    </div>
  )
}

function FaqCard({ faq, onEdit, onDelete, onToggle }) {
  const cat = getCategoryMeta(faq.faq_category)

  return (
    <div
      className={`px-5 py-4 flex items-start gap-4 group transition-colors hover:bg-accent/50 ${
        !faq.faq_is_active ? "opacity-50" : ""
      }`}
    >
      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-foreground leading-snug">
          {faq.faq_question}
        </p>
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
          {faq.faq_answer}
        </p>
        <div className="flex items-center gap-3 mt-2">
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-border text-muted-foreground font-normal">
            {cat.icon} {cat.label}
          </Badge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground/60">
            <Eye className="w-3 h-3" />
            {faq.faq_view_count ?? 0}
          </span>
          {!faq.faq_is_active && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-red-300 text-red-600 bg-red-50">
              Inactiva
            </Badge>
          )}
        </div>
      </div>

      {/* Actions — visible on hover */}
      <div
        className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 pt-0.5"
        onClick={(e) => e.stopPropagation()}
      >
        <Switch
          checked={faq.faq_is_active}
          onCheckedChange={() => onToggle(faq)}
        />
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
          onClick={() => onEdit(faq)}
        >
          <Pencil className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-destructive/60 hover:text-destructive hover:bg-red-50"
          onClick={() => onDelete(faq.faq_id)}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  )
}

export default function FAQ() {
  const [faqs, setFaqs] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const fetchFaqs = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${API}/faqitems`)
      setFaqs(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchFaqs() }, [])

  const openNew = () => {
    setEditing(null)
    setForm(emptyForm)
    setDialogOpen(true)
  }

  const openEdit = (faq) => {
    setEditing(faq.faq_id)
    setForm({
      faq_category: faq.faq_category?.toLowerCase() || "general",
      faq_question: faq.faq_question,
      faq_answer: faq.faq_answer,
      faq_is_active: faq.faq_is_active,
      faq_display_order: faq.faq_display_order || 0,
    })
    setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!form.faq_question.trim() || !form.faq_answer.trim()) {
      alert("La pregunta y respuesta son requeridas")
      return
    }
    setSaving(true)
    try {
      if (editing) {
        await axios.put(`${API}/faqitems/${editing}`, form)
      } else {
        await axios.post(`${API}/faqitems`, form)
      }
      setDialogOpen(false)
      fetchFaqs()
    } catch (err) {
      console.error(err)
      alert("Error: " + (err.response?.data?.detail || err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm("¿Eliminar esta entrada?")) return
    try {
      await axios.delete(`${API}/faqitems/${id}`)
      fetchFaqs()
    } catch (err) {
      console.error(err)
    }
  }

  const handleToggleActive = async (faq) => {
    try {
      await axios.put(`${API}/faqitems/${faq.faq_id}`, {
        faq_category: faq.faq_category?.toLowerCase() || "general",
        faq_question: faq.faq_question,
        faq_answer: faq.faq_answer,
        faq_is_active: !faq.faq_is_active,
        faq_display_order: faq.faq_display_order || 0,
      })
      fetchFaqs()
    } catch (err) {
      console.error(err)
    }
  }

  // Filter by search
  const filtered = search.trim()
    ? faqs.filter((f) =>
        f.faq_question.toLowerCase().includes(search.toLowerCase()) ||
        f.faq_answer.toLowerCase().includes(search.toLowerCase())
      )
    : faqs

  const groups = groupByCategory(filtered)

  return (
    <div>
      <TopBar title="Base de Conocimiento">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Buscar pregunta..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 w-56 h-9 text-sm"
          />
        </div>
        <Button onClick={openNew} className="transition-colors">
          <Plus className="w-4 h-4 mr-1.5" />
          Agregar FAQ
        </Button>
      </TopBar>

      {/* FAQ list */}
      {loading ? (
        <div className="space-y-6">
          {[1, 2].map((g) => (
            <div key={g}>
              <Skeleton className="h-4 w-28 mb-2" />
              <div className="bg-card rounded-xl border border-border/50 shadow-sm divide-y divide-border/50 overflow-hidden">
                {[1, 2, 3].map((i) => <FaqCardSkeleton key={i} />)}
              </div>
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <MessageCircle className="w-12 h-12 text-muted-foreground/40 mb-4" />
          <p className="text-base font-semibold text-foreground">
            {search ? "Sin resultados" : "No hay entradas aún"}
          </p>
          <p className="text-sm text-muted-foreground mt-1 max-w-xs">
            {search
              ? `No se encontraron FAQs con "${search}"`
              : "Agrega preguntas frecuentes para que el chatbot pueda responderlas"}
          </p>
          {!search && (
            <Button onClick={openNew} className="mt-5">
              <Plus className="w-4 h-4 mr-1.5" />
              Agregar primera FAQ
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups).map(([cat, items]) => {
            const meta = getCategoryMeta(cat)
            return (
              <div key={cat}>
                <div className="flex items-center gap-2 px-1 mb-2">
                  <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {meta.icon} {meta.label}
                  </h2>
                  <span className="text-xs text-muted-foreground/60">{items.length}</span>
                </div>
                <div className="bg-card rounded-xl border border-border/50 shadow-sm hover:shadow-md transition-shadow divide-y divide-border/50 overflow-hidden">
                  {items.map((faq) => (
                    <FaqCard
                      key={faq.faq_id}
                      faq={faq}
                      onEdit={openEdit}
                      onDelete={handleDelete}
                      onToggle={handleToggleActive}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar FAQ" : "Nueva FAQ"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-medium text-muted-foreground">Categoría</Label>
              <Select
                value={form.faq_category}
                onValueChange={(v) => setForm({ ...form, faq_category: v })}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.icon} {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium text-muted-foreground">
                Pregunta <span className="text-destructive">*</span>
              </Label>
              <Input
                value={form.faq_question}
                onChange={(e) => setForm({ ...form, faq_question: e.target.value })}
                placeholder="¿Cómo hago un pedido?"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs font-medium text-muted-foreground">
                Respuesta <span className="text-destructive">*</span>
              </Label>
              <Textarea
                value={form.faq_answer}
                onChange={(e) => setForm({ ...form, faq_answer: e.target.value })}
                placeholder="Puedes hacer tu pedido directamente por WhatsApp..."
                rows={4}
                className="mt-1"
              />
            </div>
            <div className="flex items-center gap-2.5 pt-1">
              <Switch
                checked={form.faq_is_active}
                onCheckedChange={(v) => setForm({ ...form, faq_is_active: v })}
              />
              <Label className="text-sm">Activa (visible para el chatbot)</Label>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto">
              {saving ? "Guardando..." : editing ? "Guardar cambios" : "Crear"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
