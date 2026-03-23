import { useState } from "react"
import { ImageIcon } from "lucide-react"
import {
  Dialog, DialogContent, DialogTitle,
} from "@/components/ui/dialog"

export default function ImageLightbox({ src, alt, className = "w-20 h-20 rounded-lg object-cover" }) {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState(false)

  if (!src || error) {
    return (
      <div className={`${className} bg-muted flex items-center justify-center flex-shrink-0`}>
        <ImageIcon className="w-7 h-7 text-muted-foreground/40" />
      </div>
    )
  }

  return (
    <>
      <button
        type="button"
        className="cursor-zoom-in flex-shrink-0 rounded-lg overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => setOpen(true)}
      >
        <img
          src={src}
          alt={alt}
          className={className}
          onError={() => setError(true)}
        />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl p-2 bg-black/95 border-none [&>button]:text-white/70 [&>button]:hover:text-white">
          <DialogTitle className="sr-only">{alt}</DialogTitle>
          <img
            src={src}
            alt={alt}
            className="w-full h-auto max-h-[80vh] object-contain rounded-lg"
          />
          <p className="text-center text-white/70 text-sm mt-2">{alt}</p>
        </DialogContent>
      </Dialog>
    </>
  )
}
