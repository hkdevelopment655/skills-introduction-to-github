import mongoose from 'mongoose';

const tryOnSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
  product: { type: mongoose.Schema.Types.ObjectId, ref: 'Product' },
  personPath: { type: String },
  resultPath: { type: String },
  method: { type: String },
  sdUsed: { type: Boolean, default: false },
}, { timestamps: true });

export default mongoose.model('TryOnResult', tryOnSchema);
