import { test, expect } from '@playwright/test';
import { fixture, login } from './intake-fixture';

test('persisted OCR edits, revision and confirmation precede explicit safety requests (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc',{exact:true}).setInputFiles('public/assets/prescription-sample.png');
  await page.getByRole('button',{name:'Đọc thông tin từ ảnh',exact:true}).click();
  const pane=page.getByRole('region',{name:'Bản nháp đã lưu trên máy chủ'});
  const confirm=pane.getByRole('button',{name:'Xác nhận danh sách',exact:true});
  await expect(confirm).toBeDisabled();
  await page.getByLabel('Tên thuốc #1',{exact:true}).fill('Panadol Viên Sủi');
  await page.getByLabel('Dạng thuốc #1',{exact:true}).fill('Viên sủi');
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('một viên');
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  await pane.getByRole('checkbox').check();await expect(confirm).toBeEnabled();
  await page.getByLabel('Thời điểm #1',{exact:true}).fill('mỗi sáng sau ăn');await expect(confirm).toBeDisabled();
  expect(state.calls.some(c=>c.path.endsWith('/confirm')||c.path.endsWith('/actions'))).toBe(false);
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  await pane.getByRole('checkbox').check();await confirm.dblclick();
  await expect(page.getByRole('button',{name:'Nhận diện và đánh giá tương tác',exact:true})).toBeEnabled();
  expect(state.calls.filter(c=>c.path.endsWith('/confirm'))).toHaveLength(1);
  expect(state.calls.filter(c=>c.path.endsWith('/actions'))).toHaveLength(0);
  await page.getByRole('button',{name:'Nhận diện và đánh giá tương tác',exact:true}).click();
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toContainText('PARTIAL');
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toContainText('không có nghĩa là an toàn');
  await page.getByRole('button',{name:'Sửa danh sách đã xác nhận',exact:true}).click();
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toHaveCount(0);
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('hai viên');
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  expect(state.review.entries[0].confirmed).toBe(false);
  expect(state.review.entries[0].medication.administrations?.[0].timing_raw).toBe('mỗi sáng sau ăn');
});

test('crop coordinates reach Core OCR without exposing engine diagnostics (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc',{exact:true}).setInputFiles('public/assets/prescription-sample.png');
  await page.getByText('Chọn vùng cần đọc',{exact:false}).click();
  await page.getByRole('button',{name:'Điều chỉnh bằng bàn phím',exact:true}).click();
  await page.getByLabel('Phải',{exact:true}).fill('62');
  await page.getByRole('button',{name:'Đọc thông tin từ ảnh',exact:true}).click();
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveValue('Panadol Viên Sui');
  expect(state.crop).toContain('name="region"');expect(state.crop).toContain('"right":0.62');
  await expect(page.getByText('engine-private-diagnostic',{exact:false})).toHaveCount(0);
});

test('manual catalog preserves second product and build through form edits; double click sends once (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake?mode=manual');
  await page.getByLabel('Tìm thuốc trong danh mục',{exact:true}).fill('Lenalimid');
  await page.getByRole('button',{name:'Tìm sản phẩm',exact:true}).click();
  await expect(page.getByRole('button',{name:/^Chọn Lenalimid/})).toHaveCount(2);
  await expect(page.getByRole('button',{name:'Lưu thuốc vào bản nháp',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Chọn Lenalimid — catalog-2',exact:true}).click();
  await page.getByLabel('Hàm lượng theo nhãn',{exact:true}).fill('10 mg');
  await page.getByLabel('Liều mỗi lần',{exact:true}).fill('một viên');
  await page.getByRole('button',{name:'Lưu thuốc vào bản nháp',exact:true}).dblclick();
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveValue('Lenalimid');
  const saved=state.calls.filter(c=>c.path.endsWith('/manual'));
  expect(saved).toHaveLength(1);expect(saved[0].body.source_medication_id).toBe('catalog-2');expect(saved[0].body.dataset_build).toBe('b'.repeat(64));
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('hai viên');
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  await expect.poll(()=>state.review.entries[0].medication.dose_raw).toBe('hai viên');
  expect(state.calls.at(-1)!.body.source_medication_id).toBe('catalog-2');
  expect(state.calls.some(c=>c.path.endsWith('/actions'))).toBe(false);
});

test('Voice retains editable transcript after invalid audio and submits the reviewed text (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake?mode=voice');
  await page.getByLabel('Tải âm thanh',{exact:true}).setInputFiles({name:'fixture.wav',mimeType:'audio/wav',buffer:Buffer.from('HTTP fixture, not real audio')});
  await page.getByRole('button',{name:'Chuyển thành văn bản',exact:true}).click();
  await expect(page.getByTestId('raw-transcript')).toHaveText('Panadone năm trăm miligam');
  await page.getByLabel('Bản chép lời để gửi',{exact:true}).fill('Panadol 500 mg, hai viên');
  await page.getByLabel('Tải âm thanh',{exact:true}).setInputFiles({name:'empty.wav',mimeType:'audio/wav',buffer:Buffer.alloc(0)});
  await page.getByRole('button',{name:'Chuyển thành văn bản',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('INVALID_AUDIO');
  await expect(page.getByLabel('Bản chép lời để gửi',{exact:true})).toHaveValue('Panadol 500 mg, hai viên');
  await page.getByRole('button',{name:'Đã xem transcript — gửi vào chatbot',exact:true}).dblclick();
  await expect(page.getByLabel('Liều mỗi lần #1',{exact:true})).toHaveValue('hai viên');
  expect(state.calls.filter(c=>c.path.endsWith('/voice/submit'))).toHaveLength(1);
  expect(state.calls.some(c=>c.path.endsWith('/confirm')||c.path.endsWith('/actions'))).toBe(false);
});

test('chat renders backend QA and does not create a local medication draft; expiry clears medical UI (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/chat');
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Thuốc X có hàm lượng bao nhiêu?');
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  await expect(page.getByRole('region',{name:'Câu trả lời có nguồn'})).toContainText('UNASSESSED');
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveCount(0);
  expect(state.review.entries).toHaveLength(0);
  await page.route('**/api/v1/intake/messages',route=>route.fulfill({status:401,json:{error:{message:'Phiên đã hết hạn'}}}));
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Bổ sung thông tin');
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
  await expect(page.getByRole('region',{name:'Bản nháp đã lưu trên máy chủ'})).toHaveCount(0);
});

test('API failures and denied microphone retain input and never display sample safety results (HTTP fixtures)',async({page})=>{
  await page.addInitScript(()=>{Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:()=>Promise.reject(new DOMException('denied','NotAllowedError'))}})});
  await fixture(page);await login(page);await page.goto('/intake?mode=voice');
  await page.getByRole('button',{name:'Thu âm',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Microphone');
  await page.getByRole('button',{name:'Chatbot',exact:true}).click();
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Dữ liệu chưa gửi được');
  await page.route('**/api/v1/intake/messages',route=>route.fulfill({status:503,json:{error:{message:'Máy chủ đang bận'}}}));
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Máy chủ đang bận');
  await expect(page.getByLabel('Tin nhắn',{exact:true})).toHaveValue('Dữ liệu chưa gửi được');
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toHaveCount(0);
});
