/* Image-driven local OCR. It never reads a medication list or ground truth. */
const fs = require('node:fs');
const path = require('node:path');
const {createWorker} = require('./ocr/node_modules/tesseract.js');

const input = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
// Optional local experiment settings; the API keeps its existing defaults.
const options = process.argv[4] ? JSON.parse(fs.readFileSync(process.argv[4], 'utf8')) : {};

function weights(directory) {
  let result = [];
  for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...weights(target));
    else if (entry.name.endsWith('.traineddata.gz')) result.push(target);
  }
  return result;
}

(async () => {
  const started = Date.now();
  const langPath = path.join(__dirname, 'ocr', 'tessdata');
  fs.mkdirSync(langPath, {recursive: true});
  for (const lang of ['vie', 'eng']) {
    const modelRoot = path.join(__dirname, 'ocr', 'node_modules', '@tesseract.js-data', lang);
    const files = weights(modelRoot);
    const source = files.find(item => item.includes('best_int')) || files[0];
    if (!source) throw new Error(`Local OCR weights missing for ${lang}`);
    const target = path.join(langPath, `${lang}.traineddata.gz`);
    if (!fs.existsSync(target)) fs.copyFileSync(source, target);
  }

  const worker = await createWorker('vie+eng', 1, {
    langPath,
    cachePath: langPath,
    workerPath: require.resolve('./ocr/node_modules/tesseract.js/src/worker-script/node/index.js'),
    corePath: path.join(__dirname, 'ocr', 'node_modules', 'tesseract.js-core')
  });
  try {
    await worker.setParameters({preserve_interword_spaces: '1', tessedit_pageseg_mode: String(options.psm ?? 3)});
    const result = await worker.recognize(input, options.rectangle ? {rectangle: options.rectangle} : {}, {text: true, blocks: true, tsv: true});
    const words = [];
    for (const block of result.data.blocks || [])
      for (const paragraph of block.paragraphs || [])
        for (const line of paragraph.lines || [])
          for (const word of line.words || [])
            words.push({text: word.text, confidence: word.confidence, bbox: word.bbox});

    fs.writeFileSync(output, JSON.stringify({
      provider: 'Tesseract.js',
      version: '6.0.1',
      model: 'Tesseract LSTM',
      languages: ['vie', 'eng'],
      recognition_options: options,
      text: result.data.text,
      confidence: result.data.confidence,
      words,
      tsv: result.data.tsv,
      duration_seconds: (Date.now() - started) / 1000
    }, null, 2));
  } finally {
    await worker.terminate();
  }
})().catch(error => {
  console.error(`Local OCR failed: ${error.message}`);
  process.exitCode = 1;
});
