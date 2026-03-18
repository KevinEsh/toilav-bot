import { useState, useEffect, useRef } from "react"
import axios from "axios"
import { ImageIcon, Pencil, Trash2, Plus, MoreVertical, Search, Package } from "lucide-react"
import TopBar from "@/components/layout/TopBar"
import ImageLightbox from "@/components/shared/ImageLightbox"
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

const emptyForm = {
  p_name: "",
  p_description: "",
  p_sale_price: 0,
  p_currency: "MXN",
  p_net_content: 1,
  p_unit: "unit",
  p_is_available: true,
  categoria: "",
}

const unitOptions = [
  { value: "unit", label: "Pieza" },
  { value: "kg", label: "Kg" },
  { value: "gr", label: "Gr" },
  { value: "liter", label: "Litro" },
  { value: "ml", label: "mL" },
]

function groupByCategory(products) {
  const groups = {}
  for (const p of products) {
    const cat = p.p_properties?.categoria || "General"
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(p)
  }
  return groups
}

function ProductCardSkeleton() {
  return (
    <div className="flex items-center gap-4 px-5 py-4">
      <Skeleton className="w-20 h-20 rounded-lg flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-60" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  )
}

function ProductCard({ product, onEdit, onDelete }) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex items-center gap-4 px-5 py-4 hover:bg-accent/50 group transition-colors">
      {/* Thumbnail with lightbox */}
      <ImageLightbox
        src={product.p_image_url}
        alt={product.p_name}
        className="w-20 h-20 rounded-lg object-cover bg-muted"
      />

      {/* Product info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-semibold text-foreground text-sm leading-tight truncate">
            {product.p_name}
          </p>
          {!product.p_is_available && (
            <Badge variant="outline" className="border-red-300 text-red-600 bg-red-50 text-[10px] px-1.5 py-0">
              No disponible
            </Badge>
          )}
        </div>
        {product.p_description && (
          <p className="text-muted-foreground text-xs mt-0.5 line-clamp-1">
            {product.p_description}
          </p>
        )}
        <div className="flex items-baseline gap-1.5 mt-1.5">
          <span className="font-mono tabular-nums text-sm font-semibold text-primary">
            ${Number(product.p_sale_price).toFixed(2)}
          </span>
          <span className="text-muted-foreground text-xs">{product.p_currency}</span>
          {product.p_net_content !== 1 && (
            <span className="text-muted-foreground text-xs">
              · {product.p_net_content} {product.p_unit}
            </span>
          )}
        </div>
      </div>

      {/* Three-dot menu */}
      <div className="relative flex-shrink-0" onClick={(e) => e.stopPropagation()}>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          <MoreVertical className="w-4 h-4" />
        </Button>
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div className="absolute right-0 top-full mt-1 z-50 bg-card border border-border/50 rounded-lg shadow-md py-1 min-w-[140px]">
              <button
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-foreground hover:bg-accent transition-colors"
                onClick={() => { setMenuOpen(false); onEdit(product) }}
              >
                <Pencil className="w-3.5 h-3.5 text-muted-foreground" />
                Editar
              </button>
              <button
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-destructive hover:bg-red-50 transition-colors"
                onClick={() => { setMenuOpen(false); onDelete(product.p_id) }}
              >
                <Trash2 className="w-3.5 h-3.5" />
                Eliminar
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function Catalog() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const fileRef = useRef()

  const fetchProducts = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${API}/products`)
      setProducts(res.data)
    } catch (err) {
      console.error("Error fetching products:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchProducts() }, [])

  const openNew = () => {
    setEditing(null)
    setForm(emptyForm)
    setImageFile(null)
    setImagePreview(null)
    setDialogOpen(true)
  }

  const openEdit = (product) => {
    setEditing(product.p_id)
    setForm({
      p_name: product.p_name,
      p_description: product.p_description || "",
      p_sale_price: product.p_sale_price,
      p_currency: product.p_currency,
      p_net_content: product.p_net_content,
      p_unit: product.p_unit,
      p_is_available: product.p_is_available,
      categoria: product.p_properties?.categoria || "",
    })
    setImageFile(null)
    setImagePreview(product.p_image_url || null)
    setDialogOpen(true)
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
    e.target.value = ""
  }

  const handleSave = async () => {
    if (!form.p_name.trim()) {
      alert("El nombre del producto es requerido")
      return
    }
    setSaving(true)
    try {
      const payload = {
        p_name: form.p_name.trim(),
        p_description: form.p_description || null,
        p_sale_price: parseFloat(form.p_sale_price) || 0,
        p_currency: form.p_currency || "MXN",
        p_net_content: parseFloat(form.p_net_content) || 1,
        p_unit: form.p_unit,
        p_is_available: form.p_is_available,
        p_properties: form.categoria.trim() ? { categoria: form.categoria.trim() } : null,
      }

      let productId = editing
      if (editing) {
        await axios.put(`${API}/products/${editing}`, payload)
      } else {
        const res = await axios.post(`${API}/products`, payload)
        productId = res.data.p_id
      }

      if (imageFile && productId) {
        const fd = new FormData()
        fd.append("file", imageFile)
        await axios.post(`${API}/products/${productId}/image`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      }

      setDialogOpen(false)
      fetchProducts()
    } catch (err) {
      console.error("Error saving product:", err)
      alert("Error guardando producto: " + (err.response?.data?.detail || err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm("¿Eliminar este producto?")) return
    try {
      await axios.delete(`${API}/products/${id}`)
      fetchProducts()
    } catch (err) {
      console.error("Error deleting product:", err)
    }
  }

  // Filter by search
  const filtered = search.trim()
    ? products.filter((p) =>
        p.p_name.toLowerCase().includes(search.toLowerCase()) ||
        p.p_description?.toLowerCase().includes(search.toLowerCase())
      )
    : products

  const groups = groupByCategory(filtered)

  return (
    <div>
      <TopBar title="Catálogo">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Buscar producto..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 w-56 h-9 text-sm"
          />
        </div>
        <Button onClick={openNew} className="transition-colors">
          <Plus className="w-4 h-4 mr-1.5" />
          Agregar producto
        </Button>
      </TopBar>

      {/* Product list */}
      {loading ? (
        <div className="space-y-6">
          {[1, 2].map((g) => (
            <div key={g}>
              <Skeleton className="h-4 w-32 mb-2" />
              <div className="bg-card rounded-xl border border-border/50 shadow-sm divide-y divide-border/50 overflow-hidden">
                {[1, 2, 3].map((i) => <ProductCardSkeleton key={i} />)}
              </div>
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Package className="w-12 h-12 text-muted-foreground/40 mb-4" />
          <p className="text-base font-semibold text-foreground">
            {search ? "Sin resultados" : "No hay productos aún"}
          </p>
          <p className="text-sm text-muted-foreground mt-1 max-w-xs">
            {search
              ? `No se encontraron productos con "${search}"`
              : "Agrega tu primer producto para empezar a vender"}
          </p>
          {!search && (
            <Button onClick={openNew} className="mt-5">
              <Plus className="w-4 h-4 mr-1.5" />
              Agregar primer producto
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups).map(([category, items]) => (
            <div key={category}>
              <div className="flex items-center gap-2 px-1 mb-2">
                <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {category}
                </h2>
                <span className="text-xs text-muted-foreground/60">{items.length}</span>
              </div>
              <div className="bg-card rounded-xl border border-border/50 shadow-sm hover:shadow-md transition-shadow divide-y divide-border/50 overflow-hidden">
                {items.map((p) => (
                  <ProductCard
                    key={p.p_id}
                    product={p}
                    onEdit={openEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar producto" : "Nuevo producto"}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Image upload with drag-and-drop zone */}
            <div>
              <Label className="text-xs font-medium text-muted-foreground">Imagen</Label>
              <div
                className="mt-1.5 border-2 border-dashed border-border rounded-lg p-4 flex items-center gap-4 hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-primary") }}
                onDragLeave={(e) => { e.currentTarget.classList.remove("border-primary") }}
                onDrop={(e) => {
                  e.preventDefault()
                  e.currentTarget.classList.remove("border-primary")
                  const file = e.dataTransfer.files[0]
                  if (file && file.type.startsWith("image/")) {
                    setImageFile(file)
                    setImagePreview(URL.createObjectURL(file))
                  }
                }}
              >
                {imagePreview ? (
                  <ImageLightbox
                    src={imagePreview}
                    alt="Vista previa"
                    className="w-20 h-20 rounded-lg object-cover bg-muted"
                  />
                ) : (
                  <div className="w-20 h-20 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                    <ImageIcon className="w-7 h-7 text-muted-foreground/40" />
                  </div>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">
                    {imagePreview ? "Cambiar imagen" : "Arrastra una imagen o haz clic"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    JPG, PNG o WebP
                  </p>
                  {imagePreview && (
                    <button
                      type="button"
                      className="text-xs text-destructive hover:underline mt-1"
                      onClick={(e) => {
                        e.stopPropagation()
                        setImageFile(null)
                        setImagePreview(null)
                      }}
                    >
                      Quitar imagen
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div>
              <Label className="text-xs font-medium text-muted-foreground">
                Nombre <span className="text-destructive">*</span>
              </Label>
              <Input
                value={form.p_name}
                onChange={(e) => setForm({ ...form, p_name: e.target.value })}
                placeholder="Ej: Nuez garapiñada 500g"
                className="mt-1"
              />
            </div>

            <div>
              <Label className="text-xs font-medium text-muted-foreground">Descripción</Label>
              <Textarea
                value={form.p_description}
                onChange={(e) => setForm({ ...form, p_description: e.target.value })}
                placeholder="Descripción breve del producto..."
                rows={2}
                className="mt-1"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-medium text-muted-foreground">
                  Precio de venta <span className="text-destructive">*</span>
                </Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.p_sale_price}
                  onChange={(e) => setForm({ ...form, p_sale_price: e.target.value === "" ? "" : parseFloat(e.target.value) })}
                  className="mt-1 font-mono"
                />
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Moneda</Label>
                <Input
                  value={form.p_currency}
                  maxLength={3}
                  onChange={(e) => setForm({ ...form, p_currency: e.target.value.toUpperCase() })}
                  className="mt-1"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Contenido neto</Label>
                <Input
                  type="number"
                  min="0"
                  step="any"
                  value={form.p_net_content}
                  onChange={(e) => setForm({ ...form, p_net_content: e.target.value === "" ? "" : parseFloat(e.target.value) })}
                  className="mt-1"
                />
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Unidad</Label>
                <Select value={form.p_unit} onValueChange={(val) => setForm({ ...form, p_unit: val })}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {unitOptions.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label className="text-xs font-medium text-muted-foreground">Categoría</Label>
              <Input
                value={form.categoria}
                onChange={(e) => setForm({ ...form, categoria: e.target.value })}
                placeholder="Ej: Frutos secos"
                className="mt-1"
              />
            </div>

            <div className="flex items-center gap-2.5 pt-1">
              <Switch
                checked={form.p_is_available}
                onCheckedChange={(val) => setForm({ ...form, p_is_available: val })}
              />
              <Label className="text-sm">Disponible para venta</Label>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto">
              {saving ? "Guardando..." : editing ? "Guardar cambios" : "Crear producto"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
