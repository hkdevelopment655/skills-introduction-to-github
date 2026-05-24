import { useState, useRef, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  Upload, Loader, Bookmark, CheckCircle,
  Sparkles, Zap, Shirt, Search, ArrowLeft, X
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import Navbar from '../components/layout/Navbar'
import api from '../services/api'

export default function VirtualTryOnPage() {
  const [params]  = useSearchParams()
  const navigate  = useNavigate()
  const productId = params.get('productId')
  const personRef = useRef(null)

  // step: 'select-shirt' | 'upload' | 'processing' | 'result'
  const [step,            setStep]           = useState(productId ? 'upload' : 'select-shirt')
  const [shirts,          setShirts]         = useState([])
  const [shirtsLoading,   setShirtsLoading]  = useState(false)
  const [search,          setSearch]         = useState('')
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [personImage,     setPersonImage]    = useState(null)
  const [personPreview,   setPersonPreview]  = useState(null)
  const [result,          setResult]         = useState(null)
  const [processing,      setProcessing]     = useState(false)
  const [sdStatus,        setSdStatus]       = useState(null)
  const [useModel,        setUseModel]       = useState(false)

  // ── SD status ──────────────────────────────────────────────────────────────
  useEffect(() => {
    api.get('/ai/sd-status')
      .then(r => setSdStatus(r.data))
      .catch(() => setSdStatus({ sdAvailable: false }))
  }, [])

  // ── Pre-select product from URL ────────────────────────────────────────────
  useEffect(() => {
    if (!productId) return
    api.get(`/products/${productId}`)
      .then(r => { setSelectedProduct(r.data.product); setStep('upload') })
      .catch(() => setStep('select-shirt'))
  }, [productId])

  // ── Fetch shirt catalogue ──────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'select-shirt') return
    setShirtsLoading(true)
    api.get('/products', { params: { category: 'shirts', limit: 50 } })
      .then(r => setShirts(r.data.products || r.data || []))
      .catch(() => setShirts([]))
      .finally(() => setShirtsLoading(false))
  }, [step])

  const filteredShirts = shirts.filter(s =>
    !search ||
    s.name?.toLowerCase().includes(search.toLowerCase()) ||
    s.brand?.toLowerCase().includes(search.toLowerCase())
  )

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleShirtSelect = (shirt) => {
    setSelectedProduct(shirt)
    setStep('upload')
    toast.success(`"${shirt.name}" selected!`)
  }

  const handlePersonSelect = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 15 * 1024 * 1024) return toast.error('Max file size is 15 MB')
    setPersonImage(file)
    setPersonPreview(URL.createObjectURL(file))
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) handlePersonSelect({ target: { files: [file] } })
  }

  const resetAll = () => {
    setStep('select-shirt')
    setResult(null)
    setPersonImage(null)
    setPersonPreview(null)
    setSelectedProduct(null)
    setSearch('')
  }

  // ── Main try-on runner ─────────────────────────────────────────────────────
  const runTryOn = async () => {
    if (!personImage)     return toast.error('Please upload your photo first.')
    if (!selectedProduct) return toast.error('Please select a shirt first.')

    setProcessing(true)
    setStep('processing')

    try {
      // ── Route through Node backend (avoids CORS + handles auth + fetches garment)
      const formData = new FormData()
      formData.append('image',           personImage)
      formData.append('productId',       selectedProduct._id || selectedProduct.id || '')
      formData.append('productName',     selectedProduct.name || '')
      formData.append('productColor',    selectedProduct.colors?.[0] || '')
      formData.append('productCategory', selectedProduct.category || 'shirts')
      if (useModel) formData.append('useModel', 'true')

      // api has the auth token baked in and uses the Node backend (port 5000)
      const { data } = await api.post('/ai/tryon', formData, {
        timeout: 120_000,   // 2 minutes — SD inpainting can be slow
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      if (!data || (!data.overlayImage && !data.result_image)) {
        throw new Error('AI service returned no image')
      }

      const overlayImage = data.overlayImage || data.result_image

      setResult({
        overlayImage,
        fitAnalysis:       data.fitAnalysis    ?? 85,
        predictedSize:     data.predictedSize  ?? 'M',
        fitType:           data.fitType        ?? 'Relaxed',
        shoulderSpan:      data.shoulderSpan   ?? null,
        torsoAlignment:    data.torsoAlignment ?? null,
        landmarksDetected: data.landmarksDetected ?? 0,
        method:            data.method         ?? 'opencv-overlay',
        sdUsed:            data.sdUsed         ?? false,
        curatorNote:       data.curatorNote    ?? 'Pose detected and garment overlay applied.',
      })
      setStep('result')

      if (data.sdUsed) toast.success('✨ Generated with Stable Diffusion!')
      else             toast.success('✅ Virtual try-on complete!')

    } catch (err) {
      console.error('Try-on error:', err)
      const msg = err?.response?.data?.message || err.message || 'Unknown error'
      toast.error(`Try-on failed: ${msg}`)
      setStep('upload')   // let the user try again rather than silently showing nothing
    } finally {
      setProcessing(false)
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <AnimatePresence mode="wait">

        {/* ════════════════════════════════════════════════════════════════
            STEP 1 — Pick a shirt
        ════════════════════════════════════════════════════════════════ */}
        {step === 'select-shirt' && (
          <motion.div key="select-shirt"
            initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0, y:-16 }}
            className="max-w-5xl mx-auto px-6 py-10"
          >
            <div className="text-center mb-8">
              {sdStatus && (
                <div className={`inline-flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full mb-4 ${
                  sdStatus.sdAvailable
                    ? 'bg-green-50 text-green-700 border border-green-200'
                    : 'bg-amber-50 text-amber-700 border border-amber-200'
                }`}>
                  {sdStatus.sdAvailable
                    ? <><Zap size={11}/> Stable Diffusion XL ready</>
                    : <><Sparkles size={11}/> MediaPipe overlay mode</>}
                </div>
              )}
              <h1 className="font-display text-4xl font-bold text-gray-900 mb-2">
                Virtual Try-On
              </h1>
              <p className="text-gray-500">Step 1 of 2 — Pick a shirt from our collection</p>
            </div>

            {/* Search */}
            <div className="relative max-w-md mx-auto mb-8">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
              <input
                type="text" placeholder="Search shirts…" value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm
                           focus:outline-none focus:ring-2 focus:ring-brand-primary"
              />
              {search && (
                <button onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  <X size={14}/>
                </button>
              )}
            </div>

            {/* Grid */}
            {shirtsLoading ? (
              <div className="flex justify-center py-20">
                <Loader size={28} className="animate-spin text-brand-primary"/>
              </div>
            ) : filteredShirts.length === 0 ? (
              <div className="text-center py-20 text-gray-400">
                <Shirt size={40} className="mx-auto mb-3 opacity-30"/>
                <p>No shirts found{search ? ` for "${search}"` : ''}.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-5">
                {filteredShirts.map(shirt => (
                  <motion.button key={shirt._id || shirt.id}
                    whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
                    onClick={() => handleShirtSelect(shirt)}
                    className="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm
                               hover:shadow-md hover:border-brand-primary transition-all text-left group"
                  >
                    <div className="relative aspect-square bg-gray-50 overflow-hidden">
                      <img
                        src={shirt.images?.[0] || shirt.image || 'https://placehold.co/300x300?text=Shirt'}
                        alt={shirt.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <div className="absolute inset-0 bg-brand-primary/0 group-hover:bg-brand-primary/10
                                      transition-colors flex items-center justify-center">
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity
                                         bg-brand-primary text-white text-xs font-bold px-3 py-1.5 rounded-full">
                          Try This On
                        </span>
                      </div>
                    </div>
                    <div className="p-3">
                      <p className="font-semibold text-gray-800 text-sm truncate">{shirt.name}</p>
                      <p className="text-xs text-gray-400 truncate">{shirt.brand}</p>
                      <p className="text-xs font-bold text-brand-primary mt-1">
                        Rs. {shirt.price?.toLocaleString()}
                      </p>
                    </div>
                  </motion.button>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* ════════════════════════════════════════════════════════════════
            STEP 2 — Upload photo
        ════════════════════════════════════════════════════════════════ */}
        {step === 'upload' && (
          <motion.div key="upload"
            initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0, y:-16 }}
            className="max-w-2xl mx-auto px-6 py-10 text-center"
          >
            <button onClick={() => { setStep('select-shirt'); setPersonImage(null); setPersonPreview(null) }}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 mb-6 transition-colors">
              <ArrowLeft size={15}/> Back to shirt selection
            </button>

            {/* Step indicator */}
            <div className="flex items-center justify-center gap-3 mb-6">
              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                <span className="w-5 h-5 rounded-full bg-brand-primary text-white flex items-center justify-center font-bold text-xs">✓</span>
                Shirt selected
              </div>
              <div className="w-8 h-px bg-gray-300"/>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-primary">
                <span className="w-5 h-5 rounded-full bg-brand-primary text-white flex items-center justify-center font-bold text-xs">2</span>
                Upload your photo
              </div>
            </div>

            <h1 className="font-display text-3xl font-bold text-gray-900 mb-2">Upload Your Photo</h1>
            <p className="text-gray-500 mb-6">Use a clear, well-lit front-facing photo for best results.</p>

            {/* Selected shirt card */}
            {selectedProduct && (
              <div className="bg-white border border-gray-100 rounded-2xl p-4 mb-6 flex items-center gap-4 text-left">
                <img
                  src={selectedProduct.images?.[0] || selectedProduct.image || 'https://placehold.co/64x64'}
                  alt={selectedProduct.name}
                  className="w-16 h-16 object-cover rounded-xl flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-800 text-sm truncate">{selectedProduct.name}</p>
                  <p className="text-xs text-gray-400">{selectedProduct.brand} · Rs. {selectedProduct.price?.toLocaleString()}</p>
                  {selectedProduct.colors?.[0] && (
                    <span className="inline-block mt-1 text-xs bg-brand-bg text-brand-primary px-2 py-0.5 rounded-full capitalize">
                      {selectedProduct.colors[0]}
                    </span>
                  )}
                </div>
                <button onClick={() => { setStep('select-shirt'); setPersonImage(null); setPersonPreview(null) }}
                  className="text-xs text-brand-primary underline flex-shrink-0">
                  Change
                </button>
              </div>
            )}

            {/* Drop zone */}
            <div onDrop={handleDrop} onDragOver={e => e.preventDefault()}
              onClick={() => personRef.current?.click()}
              className="bg-brand-primary rounded-2xl p-14 flex flex-col items-center cursor-pointer
                         hover:bg-brand-dark transition-colors"
            >
              {personPreview ? (
                <>
                  <img src={personPreview} alt="Preview" className="w-36 h-36 object-cover rounded-xl mb-4"/>
                  <p className="text-white font-semibold text-base">Photo selected ✓</p>
                  <p className="text-blue-200 text-xs mt-1">Click to change</p>
                </>
              ) : (
                <>
                  <div className="bg-white/20 p-5 rounded-2xl mb-5">
                    <Upload size={36} className="text-white"/>
                  </div>
                  <h3 className="font-semibold text-white text-lg mb-1">Drag & drop your photo here</h3>
                  <p className="text-blue-300 text-sm mb-4">JPG, PNG, WEBP — max 15 MB</p>
                  <div className="text-blue-300 text-xs mb-4">OR</div>
                  <div className="bg-yellow-400 text-gray-900 font-bold text-sm tracking-widest py-3 px-8 rounded-full">
                    UPLOAD PHOTO
                  </div>
                </>
              )}
            </div>
            <input ref={personRef} type="file" accept="image/*" className="hidden" onChange={handlePersonSelect}/>

            {/* Tips */}
            <div className="mt-5 grid grid-cols-3 gap-3 text-center">
              {[{ e:'💡', t:'Good lighting' },{ e:'🧍', t:'Front-facing' },{ e:'📏', t:'Full body visible' }].map(({ e, t }) => (
                <div key={t} className="bg-white rounded-xl p-3 border border-gray-100">
                  <div className="text-xl mb-1">{e}</div>
                  <p className="text-xs text-gray-500">{t}</p>
                </div>
              ))}
            </div>

            {personPreview && (
              <div className="mt-6">
                <label className="flex items-center gap-3 justify-center text-sm text-gray-600 mb-4">
                  <input type="checkbox" checked={useModel} onChange={e => setUseModel(e.target.checked)} className="w-4 h-4"/>
                  Use ML model (if available)
                </label>
                <button onClick={runTryOn}
                  className="btn-primary mx-auto justify-center py-4 px-10 text-base rounded-xl">
                  {sdStatus?.sdAvailable
                    ? <><Zap size={16}/> Generate with Stable Diffusion</>
                    : <><Sparkles size={16}/> Try It On</>}
                </button>
              </div>
            )}
          </motion.div>
        )}

        {/* ════════════════════════════════════════════════════════════════
            STEP 3 — Processing
        ════════════════════════════════════════════════════════════════ */}
        {step === 'processing' && (
          <motion.div key="processing"
            initial={{ opacity:0 }} animate={{ opacity:1 }}
            className="flex flex-col items-center justify-center py-32 px-8 text-center"
          >
            <div className="bg-brand-primary w-20 h-20 rounded-full flex items-center justify-center mb-6 animate-pulse">
              <Loader size={32} className="text-white animate-spin"/>
            </div>
            <h2 className="font-display text-2xl font-bold text-gray-800 mb-2">
              {sdStatus?.sdAvailable ? 'Rendering with Stable Diffusion…' : 'Processing Your Try-On…'}
            </h2>
            <p className="text-gray-500 text-sm max-w-sm">
              {sdStatus?.sdAvailable
                ? 'Analysing your pose, then generating a photorealistic try-on (30–60 s).'
                : 'Detecting your body landmarks and overlaying the selected shirt.'}
            </p>
            {selectedProduct && (
              <div className="mt-8 flex items-center gap-3 bg-white rounded-2xl px-5 py-3 border border-gray-100 shadow-sm">
                <img src={selectedProduct.images?.[0] || selectedProduct.image || 'https://placehold.co/48x48'}
                  alt={selectedProduct.name} className="w-12 h-12 object-cover rounded-lg"/>
                <div className="text-left">
                  <p className="text-sm font-semibold text-gray-800">{selectedProduct.name}</p>
                  <p className="text-xs text-gray-400">{selectedProduct.brand}</p>
                </div>
              </div>
            )}
            <div className="mt-6 flex flex-col gap-2 text-sm text-gray-400">
              <div>• Detecting body pose with MediaPipe</div>
              <div>• Calculating shoulder &amp; torso measurements</div>
              <div>{sdStatus?.sdAvailable ? '• Generating AI render' : '• Warping shirt to your pose via Delaunay triangulation'}</div>
              <div>• Preserving your face, hair &amp; body dimensions unchanged</div>
            </div>
          </motion.div>
        )}

        {/* ════════════════════════════════════════════════════════════════
            STEP 4 — Result
        ════════════════════════════════════════════════════════════════ */}
        {step === 'result' && result && (
          <motion.div key="result"
            initial={{ opacity:0 }} animate={{ opacity:1 }}
            className="flex h-[calc(100vh-65px)]"
          >
            {/* Left: image */}
            <div className="flex-1 relative bg-gray-900 overflow-hidden flex items-center justify-center">
              <img src={result.overlayImage} alt="Try-on result"
                className="max-w-full max-h-full object-contain"/>

              <div className={`absolute top-4 left-4 flex items-center gap-2 text-xs font-bold px-3 py-1.5 rounded-full ${
                result.method === 'pose-warped-overlay' ? 'bg-emerald-600 text-white' : result.sdUsed ? 'bg-brand-primary text-white' : 'bg-white/80 text-gray-700'
              }`}>
                {result.method === 'pose-warped-overlay'
                  ? <><Sparkles size={10}/> Pose-Aligned Warp ✓ Face Preserved</>
                  : result.sdUsed
                    ? <><Zap size={10}/> Stable Diffusion XL</>
                    : <><Sparkles size={10}/> {result.method || 'MediaPipe Overlay'}</>}
              </div>

              {result.shoulderSpan && result.landmarksDetected > 0 && (
                <div className="absolute top-[28%] left-[10%] bg-brand-primary/90 text-white text-xs font-mono py-1 px-2 rounded-full">
                  ● SHOULDER {result.shoulderSpan}
                </div>
              )}

              <button onClick={resetAll}
                className="absolute bottom-4 left-4 bg-white/20 hover:bg-white/30 text-white text-xs font-semibold px-4 py-2 rounded-full transition-colors">
                ↩ Try another shirt
              </button>

              {result.overlayImage?.startsWith('data:') && (
                <a href={result.overlayImage} download="tryon-result.jpg"
                  className="absolute bottom-4 right-4 bg-white/20 hover:bg-white/30 text-white text-xs font-semibold px-4 py-2 rounded-full transition-colors">
                  ⬇ Download
                </a>
              )}
            </div>

            {/* Right: analysis */}
            <div className="w-80 bg-white overflow-y-auto p-6 border-l border-gray-100">
              <span className={`text-xs font-semibold tracking-widest px-2 py-0.5 rounded ${
                result.method === 'pose-warped-overlay'
                  ? 'bg-emerald-50 text-emerald-700'
                  : result.sdUsed
                    ? 'bg-blue-50 text-brand-light'
                    : 'bg-gray-100 text-gray-500'
              }`}>
                {result.method === 'pose-warped-overlay' ? 'DELAUNAY WARP — FACE PRESERVED' : result.sdUsed ? 'SD GENERATED' : 'MEDIAPIPE OVERLAY'}
              </span>

              <h2 className="font-display text-2xl font-bold text-gray-900 mt-2 mb-1">
                {selectedProduct?.name || 'Virtual Try-On'}
              </h2>
              {selectedProduct && (
                <p className="text-gray-500 text-sm mb-4">
                  {selectedProduct.brand} · Rs. {selectedProduct.price?.toLocaleString()}
                </p>
              )}

              {/* Input previews */}
              <div className="flex gap-3 mb-5">
                {personPreview && (
                  <div className="flex-1 text-center">
                    <img src={personPreview} alt="You" className="w-full h-20 object-cover rounded-lg mb-1"/>
                    <p className="text-xs text-gray-400">Your Photo</p>
                  </div>
                )}
                {(selectedProduct?.images?.[0] || selectedProduct?.image) && (
                  <div className="flex-1 text-center">
                    <img src={selectedProduct.images?.[0] || selectedProduct.image}
                      alt="Shirt" className="w-full h-20 object-cover rounded-lg mb-1"/>
                    <p className="text-xs text-gray-400">Selected Shirt</p>
                  </div>
                )}
              </div>

              {/* Fit */}
              <div className="bg-gray-50 rounded-xl p-4 mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-semibold tracking-widest text-gray-500 uppercase">Fit Analysis</span>
                  <span className="text-brand-light font-bold text-sm">{result.fitAnalysis}% Optimized</span>
                </div>
                <div className="w-full h-1.5 bg-gray-200 rounded-full">
                  <motion.div className="h-full bg-brand-primary rounded-full"
                    initial={{ width:0 }} animate={{ width:`${result.fitAnalysis}%` }}
                    transition={{ duration:1, ease:'easeOut' }}/>
                </div>
              </div>

              {/* Size */}
              <div className="mb-4">
                <p className="label-sm mb-2">AI Predicted Size</p>
                <div className="flex gap-2">
                  {['S','M','L','XL'].map(s => (
                    <button key={s} className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${
                      s === result.predictedSize ? 'bg-brand-primary text-white' : 'bg-gray-100 text-gray-600'
                    }`}>{s}</button>
                  ))}
                </div>
              </div>

              {/* Fit type */}
              <div className="mb-4">
                <p className="label-sm mb-2">Fit Style</p>
                <div className="flex gap-2">
                  {['Tapered','Relaxed'].map(f => (
                    <button key={f} className={`flex-1 py-2 rounded-lg text-sm font-semibold flex items-center justify-center gap-1 transition-colors ${
                      f === result.fitType ? 'bg-brand-primary text-white' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {f} {f === result.fitType && <CheckCircle size={12}/>}
                    </button>
                  ))}
                </div>
              </div>

              {/* Curator note */}
              <div className="bg-gray-50 rounded-xl p-4 mb-4">
                <p className="label-sm mb-2">Curator's Note</p>
                <p className="font-display italic text-gray-700 text-sm leading-relaxed">
                  "{result.curatorNote}"
                </p>
              </div>

              {/* Method */}
              <div className={`rounded-xl p-3 mb-4 text-xs ${
                result.method === 'pose-warped-overlay'
                  ? 'bg-emerald-50 text-emerald-700'
                  : result.sdUsed
                    ? 'bg-brand-bg text-brand-primary'
                    : 'bg-gray-50 text-gray-500'
              }`}>
                {result.method === 'pose-warped-overlay'
                  ? '🎯 Pose-Aligned Delaunay Warp — your face, hair & body dimensions are pixel-identical to your original photo'
                  : result.sdUsed
                    ? '⚡ Stable Diffusion XL — photorealistic AI rendering'
                    : result.method === 'gemini-overlay'
                      ? '🤖 Gemini-guided MediaPipe overlay'
                      : result.method === 'color-transfer'
                        ? '🎨 Color transfer (no landmarks detected)'
                        : '📐 MediaPipe body landmark overlay'}
              </div>

              <button className="w-full btn-primary justify-center mb-3">
                <Bookmark size={14}/> SAVE TO VAULT
              </button>
              {selectedProduct && (
                <button
                  onClick={() => navigate(`/products/${selectedProduct._id || selectedProduct.id}`)}
                  className="w-full py-2.5 rounded-xl border border-brand-primary text-brand-primary text-sm font-semibold hover:bg-brand-bg transition-colors">
                  View Product Page
                </button>
              )}
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  )
}