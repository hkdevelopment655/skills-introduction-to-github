// import express from 'express';
// import cors from 'cors';
// import dotenv from 'dotenv';
// import { createServer } from 'http';
// import { Server } from 'socket.io';
// import { fileURLToPath } from 'url';
// import { dirname, join } from 'path';
// import connectDB from './config/database.js';
// import authRoutes from './routes/auth.js';
// import productRoutes from './routes/products.js';
// import chatRoutes from './routes/chat.js';
// import orderRoutes from './routes/orders.js';
// import groupCartRoutes from './routes/groupCart.js';
// import paymentRoutes from './routes/payment.js';
// import adminRoutes from './routes/admin.js';
// import giftPoolRoutes from './routes/giftPool.js';
// import aiRoutes from './routes/ai.js';
// import { errorHandler } from './middleware/errorHandler.js';
// import { setupSocketHandlers } from './utils/socketHandlers.js';

// // Always load .env from backend/ root regardless of where node is invoked from
// const __dirname = dirname(fileURLToPath(import.meta.url));
// dotenv.config({ path: join(__dirname, '../../.env') });

// // Debug: confirm key loaded (remove after confirming it works)
// console.log('🔑 GEMINI_API_KEY loaded:', process.env.GEMINI_API_KEY ? `${process.env.GEMINI_API_KEY.slice(0,8)}...` : 'NOT SET');
// connectDB();

// const app = express();
// const httpServer = createServer(app);
// const io = new Server(httpServer, {
//   cors: {
//     origin: process.env.CLIENT_URL || 'http://localhost:5173',
//     methods: ['GET', 'POST'],
//     credentials: true
//   }
// });

// // Middleware
// app.use(cors({
//   origin: process.env.CLIENT_URL || 'http://localhost:5173',
//   credentials: true
// }));
// app.use(express.json({ limit: '50mb' }));
// app.use(express.urlencoded({ extended: true, limit: '50mb' }));
// app.use('/uploads', express.static('uploads'));

// // Attach io to request
// app.use((req, res, next) => {
//   req.io = io;
//   next();
// });

// // Routes
// app.use('/api/auth', authRoutes);
// app.use('/api/products', productRoutes);
// app.use('/api/chat', chatRoutes);
// app.use('/api/orders', orderRoutes);
// app.use('/api/group-cart', groupCartRoutes);
// app.use('/api/payment', paymentRoutes);
// app.use('/api/admin', adminRoutes);
// app.use('/api/gift-pool', giftPoolRoutes);
// app.use('/api/ai', aiRoutes);

// app.get('/api/health', (req, res) => res.json({ status: 'OK', timestamp: new Date() }));

// // Socket.io handlers
// setupSocketHandlers(io);

// // Error handler
// app.use(errorHandler);

// const PORT = process.env.PORT || 5000;
// httpServer.listen(PORT, () => {
//   console.log(`🚀 Smart AI Server running on port ${PORT}`);
// });

// export default app;
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { Server } from 'socket.io';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import connectDB from './config/database.js';
import authRoutes from './routes/auth.js';
import productRoutes from './routes/products.js';
import chatRoutes from './routes/chat.js';
import orderRoutes from './routes/orders.js';
import groupCartRoutes from './routes/groupCart.js';
import paymentRoutes from './routes/payment.js';
import adminRoutes from './routes/admin.js';
import giftPoolRoutes from './routes/giftPool.js';
import aiRoutes from './routes/ai.js';
import { errorHandler } from './middleware/errorHandler.js';
import { setupSocketHandlers } from './utils/socketHandlers.js';
 
// ── Load .env ─────────────────────────────────────────────────────────────────
// server.js is at backend/src/server.js
// .env is at backend/.env
// So __dirname = backend/src  →  join one level up gives backend/.env
const __filename = fileURLToPath(import.meta.url);
const __dirname  = dirname(__filename);
const envFile    = join(__dirname, '..', '.env');   // backend/src/../.env = backend/.env
 
dotenv.config({ path: envFile });
 
// Confirm env loaded correctly
console.log('📁 .env path:', envFile);
console.log('🗄️  MONGODB_URI:', process.env.MONGODB_URI ? 'SET ✅' : 'NOT SET ❌');
console.log('🔑 GEMINI_API_KEY:', process.env.GEMINI_API_KEY ? process.env.GEMINI_API_KEY.slice(0, 10) + '...' : 'NOT SET ❌');
// ─────────────────────────────────────────────────────────────────────────────
 
connectDB();
 
const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer, {
  cors: {
    origin: process.env.CLIENT_URL || 'http://localhost:5173',
    methods: ['GET', 'POST'],
    credentials: true
  }
});
 
app.use(cors({ origin: process.env.CLIENT_URL || 'http://localhost:5173', credentials: true }));
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));
app.use('/uploads', express.static('uploads'));
 
app.use((req, res, next) => { req.io = io; next(); });
 
app.use('/api/auth',       authRoutes);
app.use('/api/products',   productRoutes);
app.use('/api/chat',       chatRoutes);
app.use('/api/orders',     orderRoutes);
app.use('/api/group-cart', groupCartRoutes);
app.use('/api/payment',    paymentRoutes);
app.use('/api/admin',      adminRoutes);
app.use('/api/gift-pool',  giftPoolRoutes);
app.use('/api/ai',         aiRoutes);
 
app.get('/api/health', (req, res) => res.json({ status: 'OK', timestamp: new Date() }));
 
setupSocketHandlers(io);
app.use(errorHandler);
 
const PORT = process.env.PORT || 5000;
httpServer.listen(PORT, () => console.log(`🚀 Smart AI Server running on port ${PORT}`));
 
export default app;