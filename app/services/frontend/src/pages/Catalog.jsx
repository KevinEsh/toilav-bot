import { useState, useEffect } from "react"
import axios from "axios"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"

const API = "http://localhost:8000"

const emptyProduct = {
  p_name: "",
  p_description: "",
  p_sale_price: 0,
  p_currency: "MXN",
  p_net_content: 1,
  p_unit: "unit",
  p_properties: null,
  p_is_available: true,
}

const unitOptions = [
  { value: "unit", label: "Pieza" },
  { value: "kg", label: "Kg" },
  { value: "gr", label: "Gr" },
  { value: "liter", label: "Litro" },
  { value: "ml", label: "mL" },
]

export default function Catalog() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyProduct)
  const [propsText, setPropsText] = useState("")

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
    setForm(emptyProduct)
    setPropsText("")
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
      p_properties: product.p_properties,
      p_is_available: product.p_is_available,
    })
    setPropsText(product.p_properties ? JSON.stringify(product.p_properties) : "")
    setDialogOpen(true)
  }

  const handleSave = async () => {
    try {
      const payload = { ...form }
      if (propsText) {
        try {
          payload.p_properties = JSON.parse(propsText)
        } catch {
          alert("Las propiedades no son JSON válido")
          return
        }
      } else {
        payload.p_properties = null
      }
      if (editing) {
        await axios.put(`${API}/products/${editing}`, payload)
      } else {
        await axios.post(`${API}/products`, payload)
      }
      setDialogOpen(false)
      fetchProducts()
    } catch (err) {
      console.error("Error saving product:", err)
      alert("Error guardando producto: " + (err.response?.data?.detail || err.message))
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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Catálogo de Productos</h1>
        <Button onClick={openNew}>+ Agregar producto</Button>
      </div>

      {loading ? (
        <p className="text-gray-500">Cargando productos...</p>
      ) : products.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No hay productos aún</p>
          <p className="text-sm mt-1">Agrega tu primer producto para empezar</p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Precio</TableHead>
                <TableHead>Contenido</TableHead>
                <TableHead>Disponible</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((p) => (
                <TableRow key={p.p_id}>
                  <TableCell className="font-medium">{p.p_name}</TableCell>
                  <TableCell>${p.p_sale_price} {p.p_currency}</TableCell>
                  <TableCell>{p.p_net_content} {p.p_unit}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      p.p_is_available
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}>
                      {p.p_is_available ? "Sí" : "No"}
                    </span>
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(p)}>
                      Editar
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => handleDelete(p.p_id)}>
                      Eliminar
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Modal crear/editar */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar producto" : "Nuevo producto"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Nombre</Label>
              <Input
                value={form.p_name}
                onChange={(e) => setForm({ ...form, p_name: e.target.value })}
                placeholder="Ej: Nuez garapiñada 500g"
              />
            </div>
            <div>
              <Label>Descripción</Label>
              <Textarea
                value={form.p_description}
                onChange={(e) => setForm({ ...form, p_description: e.target.value })}
                placeholder="Descripción del producto..."
                rows={2}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Precio de venta</Label>
                <Input
                  type="number"
                  value={form.p_sale_price}
                  onChange={(e) => setForm({ ...form, p_sale_price: e.target.value === "" ? "" : parseFloat(e.target.value) })}
                />
              </div>
              <div>
                <Label>Moneda</Label>
                <Input
                  value={form.p_currency}
                  onChange={(e) => setForm({ ...form, p_currency: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Contenido neto</Label>
                <Input
                  type="number"
                  value={form.p_net_content}
                  onChange={(e) => setForm({ ...form, p_net_content: e.target.value === "" ? "" : parseFloat(e.target.value) })}
                />
              </div>
              <div>
                <Label>Unidad</Label>
                <Select value={form.p_unit} onValueChange={(val) => setForm({ ...form, p_unit: val })}>
                  <SelectTrigger>
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
              <Label>Propiedades (ej: sabor, tamaño)</Label>
              <Input
                value={propsText}
                onChange={(e) => setPropsText(e.target.value)}
                placeholder='{"sabor": "garapiñada", "tamaño": "grande"}'
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.p_is_available}
                onCheckedChange={(val) => setForm({ ...form, p_is_available: val })}
              />
              <Label>Disponible para venta</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSave}>{editing ? "Guardar cambios" : "Crear producto"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}