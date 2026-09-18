"""Censimento e quattro test aggiuntivi, senza modificare risultati precedenti."""
import ast
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file,'sha256').hexdigest()


def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def csv_write(name,rows,fields):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if (OUT/'targeted_family_manifest.json').exists():
        raise RuntimeError('Manifest mirato già presente: nessuna sovrascrittura o riesecuzione.')
    protected=[p for folder in ('backend','frontend','scripts','evaluation')
               for p in (ROOT/'prototype'/folder).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts]
    protected.append(ROOT/'prototype/data/products_demo.json')
    before={p:sha(p) for p in protected}
    from prototype.backend.app import app,catalog
    from prototype.backend.services import recommendation_service as service
    from prototype.evaluation.contextual_recommendations.evaluate_contextual_recommendations import ServiceLog
    from fastapi.testclient import TestClient

    # Legge i nomi e il mapping dal codice, senza una copia mantenuta a mano.
    source=ROOT/'prototype/backend/services/recommendation_service.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    family_fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_product_family')
    names={n.value.value for n in ast.walk(family_fn) if isinstance(n,ast.Return)
           and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)}
    for n in ast.walk(family_fn):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='family_patterns' for t in n.targets):
            names.update(row[0] for row in ast.literal_eval(n.value))
    complement_fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_complement_terms')
    mapping=next(ast.literal_eval(n.value) for n in ast.walk(complement_fn)
                 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='family_mapping' for t in n.targets))
    products=catalog.all_products()
    counts=Counter(p.item_id for p in products)
    valid=[p for p in products if p.item_id.strip() and counts[p.item_id]==1 and p.title.strip()
           and p.category.strip() and p.price is not None and math.isfinite(p.price) and p.price>0]
    families={name:[p for p in valid if service._product_family(p)==name] for name in names}
    inventory=[]
    for name in sorted(names):
        terms=mapping.get(name,[])
        possible=[p for p in valid if any(service._title_matches_complement(p,t) for t in terms)]
        inventory.append({'Famiglia':name,'Tipologie_complementari':'; '.join(terms),
                          'N_prodotti_catalogo':sum(service._product_family(p)==name for p in products),
                          'N_prodotti_validi':len(families[name]),'N_complementari_possibili':len(possible),
                          'Mapping_presente':'Sì' if name in mapping else 'No'})
    csv_write('targeted_family_inventory.csv',inventory,list(inventory[0]))
    eligible=sorted((r for r in inventory if r['N_prodotti_validi'] and r['Tipologie_complementari']
                     and r['N_complementari_possibili']),key=lambda r:(-r['N_prodotti_validi'],r['Famiglia']))
    assert len(eligible)>=4
    raw_catalog={r['item_id']:r for r in json.loads((ROOT/'prototype/data/products_demo.json').read_bytes())}
    tests=[]
    for index,entry in enumerate(eligible[:4],1):
        family=entry['Famiglia']
        pool=families[family]
        def finite(value):
            return isinstance(value,(int,float)) and math.isfinite(value)
        key='popularity_score'
        ranked=[p for p in pool if finite(raw_catalog[p.item_id].get(key))]
        if not ranked:
            key='rating_count'
            ranked=[p for p in pool if finite(raw_catalog[p.item_id].get(key))]
        chosen=min(ranked,key=lambda p:(-raw_catalog[p.item_id][key],p.item_id)) if ranked else min(pool,key=lambda p:p.item_id)
        rule=f'Massimo {key}; parità: item_id crescente' if ranked else 'item_id crescente'
        assert service._complement_terms(chosen)==mapping[family]
        tests.append({'ID_test':f'F{index:02d}','item_id':chosen.item_id,'titolo':chosen.title,
                      'categoria':chosen.category,'prezzo':chosen.price,'famiglia_riconosciuta':family,
                      'tipologie_complementari_previste':mapping[family],
                      'popularity_score':raw_catalog[chosen.item_id].get('popularity_score'),
                      'criterio_di_selezione':rule})
    dump('targeted_family_manifest.json',{
        'created_at':datetime.now(timezone.utc).isoformat(),'selection_before_recommendations':True,
        'family_selection':'Numero prodotti validi decrescente, parità alfabetica; prime quattro ammissibili, nessuna deroga manuale.',
        'possible_complements':'Prodotti validi unici con almeno un match tramite _title_matches_complement; conteggio potenziale, non ranking né raccomandazioni.',
        'eligibility':'item_id univoco non vuoto, titolo e categoria non vuoti, prezzo finito positivo; nessun filtro sulla qualità delle raccomandazioni.',
        'catalog_sha256':sha(ROOT/'prototype/data/products_demo.json'),
        'service_sha256':sha(source),'tests':tests})
    frozen=sha(OUT/'targeted_family_manifest.json')
    print('MANIFEST CONGELATO',json.dumps(tests,ensure_ascii=True),flush=True)
    raw=OUT/'targeted_raw'
    raw.mkdir()
    fields=['ID','Item_id','Prodotto','Categoria','Famiglia','Tipologie_complementari_previste',
            'N_simili_alternative','N_utili_insieme','Prodotti_mostrati','Fallback','Nome_gruppo_simili','Nome_gruppo_complementari']
    review_fields=['ID_test','Prodotto_partenza','Famiglia_partenza','Gruppo','Item_id_raccomandato',
                   'Titolo_raccomandato','Categoria_raccomandato','Famiglia_raccomandato','Posizione_nel_gruppo','Complementarita_prevista']
    rows=[]
    review=[]
    checks=[]
    diagnostics=[]
    capture=ServiceLog()
    service.logger.addHandler(capture)
    try:
        with TestClient(app,raise_server_exceptions=False) as client:
            for test in tests:
                tid=test['ID_test']
                row=dict.fromkeys(fields,'')
                row.update(ID=tid,Item_id=test['item_id'],Prodotto=test['titolo'],Categoria=test['categoria'],
                           Famiglia=test['famiglia_riconosciuta'],Tipologie_complementari_previste='; '.join(test['tipologie_complementari_previste']))
                diag={'ID':tid,'Started_at':datetime.now(timezone.utc).isoformat(),'HTTP_status':'','Errore':'','Avvisi':''}
                capture.messages.clear()
                try:
                    response=client.get('/recommendations/contextual/'+quote(test['item_id'],safe=''),
                                        params={'limit':4,'use_ai_support':'false'})
                    diag['HTTP_status']=response.status_code
                    try:
                        data=response.json()
                    except ValueError:
                        (raw/f'{tid}.response.txt').write_bytes(response.content)
                        raise ValueError('Risposta non JSON conservata in .response.txt')
                    (raw/f'{tid}.json').write_bytes(response.content)
                    if not response.is_success:
                        raise RuntimeError(f'HTTP {response.status_code}')
                    groups=data['groups']
                    similar=[g for g in groups if g['role_id']=='similar_alternatives']
                    together=[g for g in groups if g['role_id']=='complementary']
                    row.update(N_simili_alternative=sum(len(g['products']) for g in similar),
                               N_utili_insieme=sum(len(g['products']) for g in together),
                               Prodotti_mostrati=sum(len(g['products']) for g in groups),
                               Fallback='Sì' if data['fallback'] else 'No',
                               Nome_gruppo_simili='; '.join(g['label'] for g in similar),
                               Nome_gruppo_complementari='; '.join(g['label'] for g in together))
                    for group in groups:
                        for position,product in enumerate(group['products'],1):
                            p=service.Product(**{k:product[k] for k in service.Product.model_fields if k in product})
                            family=service._product_family(p)
                            check=''
                            if group['role_id']=='complementary':
                                matches=[t for t in test['tipologie_complementari_previste'] if service._title_matches_complement(p,t)]
                                check='Sì' if matches else ('No' if family else 'Non determinabile')
                                checks.append({'ID_test':tid,'Item_id_raccomandato':p.item_id,
                                               'Famiglia_raccomandato':family or '',
                                               'Tipologie_corrispondenti':'; '.join(matches),'Complementarita_prevista':check})
                            review.append(dict(zip(review_fields,[tid,test['titolo'],test['famiglia_riconosciuta'],
                                          group['label'],p.item_id,p.title,p.category,family or '',position,check])))
                except Exception as exc:
                    diag['Errore']=f'{type(exc).__name__}: {exc}'
                    dump(f'targeted_raw/{tid}.error.json',diag)
                diag['Avvisi']='; '.join(capture.messages)
                rows.append(row)
                diagnostics.append(diag)
                csv_write('contextual_recommendations_targeted.csv',rows,fields)
                csv_write('contextual_recommendations_targeted_review.csv',review,review_fields)
                csv_write('targeted_mapping_checks.csv',checks,['ID_test','Item_id_raccomandato','Famiglia_raccomandato','Tipologie_corrispondenti','Complementarita_prevista'])
                csv_write('targeted_diagnostics.csv',diagnostics,list(diag))
                print(json.dumps(row,ensure_ascii=True),flush=True)
    finally:
        service.logger.removeHandler(capture)
        assert sha(OUT/'targeted_family_manifest.json')==frozen
        assert all(sha(p)==value for p,value in before.items()),'File preesistente modificato'
    dump('targeted_verification.json',{'completed_at':datetime.now(timezone.utc).isoformat(),
         'tests':len(rows),'review_rows':len(review),'preexisting_files_unchanged':len(before),
         'manifest_unchanged':True,'gemini_calls':0,
         'mapping_counts':{t['ID_test']:dict(Counter(c['Complementarita_prevista'] for c in checks if c['ID_test']==t['ID_test'])) for t in tests}})


if __name__=='__main__':
    main()
