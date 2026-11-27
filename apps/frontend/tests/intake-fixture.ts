import { expect, type Page } from '@playwright/test';
import type { IntakeReview, IntakeDetails, VoicePreview, MedicationFields, CatalogProduct } from '../src/api';

// HTTP fixtures test the browser contract, NOT Qwen/Whisper/Tesseract accuracy.
export async function fixture(page: Page, medication: Partial<MedicationFields> = {}) {
  const build = 'b'.repeat(64);
  const products: CatalogProduct[] = [1, 2].map(n => ({id:'product-'+n, dataset_build:build,
    source_medication_id:'catalog-'+n, brand_name:'Lenalimid', dosage_form:'Viên nang',
    manufacturer:'Nhà sản xuất '+n, registration_token:'SDK-'+n,
    components:[{ingredient_text_raw:n === 1 ? 'Lenalidomide 5 mg' : 'Lenalidomide 10 mg'}]}));
  const med: MedicationFields = {name_raw:'Panadol Viên Sui',strength_raw:'500mg',dosage_form_raw:null,dose_raw:'1 viên',
    evidence_text:'Panadol Viên Sui 500mg',administrations:[{timing_raw:'mỗi sáng',dose_raw:'1 viên',timing_slots_raw:[]}], ...medication};
  let sequence = 1;
  let review: IntakeReview = {workflow_id:'11111111-1111-4111-8111-111111111111',revision:1,state:'COLLECTING',
    assistant_message:'Hãy nhập thông tin thuốc',entries:[],missing_blockers:[],qa_results:[]};
  let sources: IntakeDetails['entry_sources'] = {};
  let assessment: IntakeDetails['assessment'] = null;
  let voice: VoicePreview = {workflow_id:review.workflow_id,revision:1,error_code:null,retry_allowed:true,draft:null};
  const calls: {path:string;body:Record<string,unknown>}[] = [];
  let crop = '';
  const nextEntry = () => '22222222-2222-4222-8222-'+String(sequence++).padStart(12,'0');
  function add(medication: MedicationFields, selected: CatalogProduct | null, inputSource: string, replace=false) {
    const entry={entry_version_id:nextEntry(),confirmed:false,medication};
    if(replace) review.entries=[entry]; else review.entries.push(entry);
    sources[entry.entry_version_id]={input_source:inputSource,selected_product:selected ? {
      medication_id:selected.id,dataset_build:build,source_medication_id:selected.source_medication_id,
      brand_name:selected.brand_name,dosage_form:selected.dosage_form}:null};
    review={...review,revision:review.revision+1,state:'AWAITING_CONFIRMATION',assistant_message:'Hãy xem lại bản nháp',qa_results:[]};
  }
  await page.route('**/api/reference/medications?*',route=>route.fulfill({json:{medications:products,dataset_build:build}}));
  await page.route('**/api/v1/intake/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/capabilities')) return route.fulfill({json:{persistent_intake:true}});
    if(path.endsWith('/details')) return route.fulfill({json:{review,conversation_id:'conversation-fixture',
      messages:[{id:'assistant-'+review.revision,role:'ASSISTANT',text_content:review.assistant_message,input_source:'TEXT'}],
      entry_sources:sources,assessment}});
    if(route.request().method()==='GET' && path.endsWith('/voice'))
      return route.fulfill({json:{...voice,workflow_id:review.workflow_id,revision:review.revision}});
    if(path.endsWith('/ocr')) {
      crop=route.request().postData() || '';
      calls.push({path,body:{}});
      add(med,null,'OCR');
      return route.fulfill({json:{review,ocr:{medication_entries:[{extracted_name:med.name_raw}],extraction_run:{raw_output:{ocr:{text:'engine-private-diagnostic'}}}}}});
    }
    const body=route.request().postDataJSON() || {};
    calls.push({path,body});
    expect(body).not.toHaveProperty('owner'); expect(body).not.toHaveProperty('user_id');
    if(path.endsWith('/workflows')) return route.fulfill({json:review});
    expect(body.revision).toBe(review.revision);
    if(!path.endsWith('/revise')) expect(body.workflow_id).toBe(review.workflow_id);
    if(path.endsWith('/manual')) add(body.medication,products.find(p=>p.source_medication_id===body.source_medication_id)!, 'MANUAL');
    else if(path.endsWith('/entries/edit')) {
      const old=review.entries.find(e=>e.entry_version_id===body.entry_version_id)!;
      const source=sources[old.entry_version_id]; const selected=products.find(p=>p.source_medication_id===body.source_medication_id)||null;
      const entry={...old,entry_version_id:nextEntry(),confirmed:false,medication:body.medication};
      review={...review,revision:review.revision+1,state:'AWAITING_CONFIRMATION',
        entries:review.entries.map(e=>e===old?entry:e)};
      sources[entry.entry_version_id]=selected?{input_source:'MANUAL',selected_product:{medication_id:selected.id,
        dataset_build:build,source_medication_id:selected.source_medication_id,brand_name:selected.brand_name}}:source;
    } else if(path.endsWith('/confirm')) {
      expect(body.explicit_confirmation).toBe(true); expect(body.request_key).toBeTruthy();
      review={...review,revision:review.revision+1,state:'COMPLETED',entries:review.entries.map(e=>({...e,confirmed:true}))};
    } else if(path.endsWith('/actions')) {
      expect(review.state).toBe('COMPLETED'); expect(body.explicit_request).toBe(true);
      assessment={execution_status:'COMPLETED',check_results:{ddi:{execution:'COMPLETED',coverage:'PARTIAL',limitations:['Chỉ kiểm tra phạm vi có dữ liệu']}},
        findings:[{finding_type:'DDI',severity:'MODERATE',source_severity:'Moderate',explanation:'Cảnh báo có bằng chứng',evidence:{source:'DDInter fixture'}}]};
      review={...review,assessment_id:'assessment-fixture',assistant_message:'Moderate · PARTIAL'};
    } else if(path.endsWith('/revise')) {
      review={...review,workflow_id:'33333333-3333-4333-8333-333333333333',revision:1,state:'CLARIFYING',assessment_id:null,
        assistant_message:'Hãy sửa và xác nhận lại'};assessment=null;
    } else if(path==='/api/v1/intake/voice') {
      if(!body.audio_payload) return route.fulfill({json:{...voice,revision:review.revision,error_code:'INVALID_AUDIO'}});
      review={...review,revision:review.revision+1};
      voice={workflow_id:review.workflow_id,revision:review.revision,error_code:null,retry_allowed:true,
        draft:{draft_id:'44444444-4444-4444-8444-444444444444',raw_transcript:'Panadone năm trăm miligam',text:'Panadone năm trăm miligam',confidence_score:.8,language:'vi-VN'}};
      return route.fulfill({json:voice});
    } else if(path.endsWith('/voice/edit')) {
      expect(body.draft_id).toBe(voice.draft!.draft_id);
      review={...review,revision:review.revision+1}; voice={...voice,revision:review.revision,draft:{...voice.draft!,text:String(body.text)}};
      return route.fulfill({json:voice});
    } else if(path.endsWith('/voice/submit')) {
      expect(body.explicit_confirmation).toBe(true); expect(voice.draft!.text).toBe('Panadol 500 mg, hai viên');
      add({...med,name_raw:'Panadol',dosage_form_raw:'Viên nén',dose_raw:'hai viên'},null,'VOICE');voice={...voice,draft:null};
    } else if(path.endsWith('/messages')) {
      review={...review,revision:review.revision+1,assistant_message:'Không đủ bằng chứng để trả lời',qa_results:[
        {text:'Câu trả lời từ backend',status:'UNAVAILABLE',coverage:'UNASSESSED',limitations:['Chưa có nguồn phù hợp'],evidence_refs:[]}]};
    } else throw new Error('Unexpected intake request '+path);
    return route.fulfill({json:review});
  });
  return {calls,products,get review(){return review;},get crop(){return crop;}};
}
export async function login(page:Page) {
  await page.addLocatorHandler(page.getByRole('button',{name:'Nhắc lại sau 7 ngày',exact:true}),async locator=>locator.click());
  await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill('mai.demo@example.com');
  await page.getByLabel('Mật khẩu',{exact:true}).fill('Mai-patient-2026');
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await expect(page).toHaveURL('/dashboard');
}

