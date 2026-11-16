import json
import unittest
from unittest.mock import patch

from prototype.backend.schemas import Product
from prototype.backend.services.discovery_service import (
    MAX_GROUP_PRODUCTS,
    discover_products,
)
from prototype.backend.services.query_utils import expand_query_terms
from prototype.backend.services.recommendation_service import contextual_recommendations
from prototype.backend.services.search_service import search_products


class EmptyEvidenceService:
    def evidence_for_product(self,**_kwargs):
        return []


class CountingEvidenceService:
    # Conta le chiamate effettuate e restituisce sempre lista vuota.
    def __init__(self):
        self.calls=[]

    def evidence_for_product(self,product,**_kwargs):
        self.calls.append(product.item_id)
        return []


def _make_products(n: int=8) -> list[Product]:
    return [
        Product(
            item_id=f"p{index}",
            title=f"Wireless Mouse Model {index}",
            category="Computer Mouse",
            description="gaming programmable" if index % 2 else "office ergonomic",
            price=10.0 + index*5,
            average_rating=4.0 + index/10,
            rating_count=100*index,
            popularity_score=1.0 - index/20,
        )
        for index in range(1,n + 1)
    ]


def _gemini_two_groups(candidate_ids: list[str]) -> str:
    # Risposta Gemini valida con due cluster usando i primi candidati disponibili.
    return json.dumps({
        "answer": "Cluster creati dinamicamente.",
        "groups": [
            {
                "cluster_id": "uso_quotidiano",
                "label": "Uso quotidiano",
                "description": "Primo cluster basato sui dati disponibili.",
                "reason": "Usa soltanto candidati locali.",
                "item_ids": [candidate_ids[0],candidate_ids[1],"inventato"],
            },
            {
                "cluster_id": "prestazioni",
                "label": "Prestazioni",
                "description": "Secondo cluster basato sui dati disponibili.",
                "reason": "Usa soltanto candidati locali.",
                "item_ids": [candidate_ids[2],candidate_ids[3]],
            },
        ],
    })


class DiscoveryServiceTest(unittest.TestCase):
    def setUp(self):
        self.products=_make_products(8)
        self.evidence_service=EmptyEvidenceService()

    # --- test esistenti aggiornati ---

    def test_gemini_creates_groups_from_local_candidate_ids(self):
        # Gemini riceve candidati locali e restituisce cluster validi.
        # Gli item_id inventati devono essere scartati.
        captured={}

        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            captured["payload"]=payload
            candidate_ids=[item["item_id"] for item in payload["candidates"]]
            return _gemini_two_groups(candidate_ids)

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            response=discover_products(
                self.products,
                "mouse",
                self.evidence_service,
                ai_query="separa per utilizzo",
            )

        product_ids=[product.item_id for group in response.groups for product in group.products]
        self.assertTrue(response.used_ai_support)
        self.assertEqual([group.role_id for group in response.groups],["uso_quotidiano","prestazioni"])
        self.assertNotIn("groups",captured["payload"])
        self.assertNotIn("inventato",product_ids)
        self.assertEqual(len(product_ids),len(set(product_ids)))

    def test_invalid_gemini_response_uses_local_fallback(self):
        # Risposta Gemini con un solo cluster invalido -> fallback locale.
        with patch(
            "prototype.backend.services.discovery_service.call_gemini",
            return_value=json.dumps({
                "answer": "Risposta non valida",
                "groups": [{
                    "cluster_id": "inventato",
                    "label": "Inventato",
                    "description": "Contiene soltanto un ID estraneo.",
                    "item_ids": ["id_inesistente"],
                }],
            }),
        ):
            response=discover_products(self.products,"mouse",self.evidence_service)

        self.assertFalse(response.used_ai_support)
        self.assertGreaterEqual(len(response.groups),1)
        self.assertEqual(response.groups[0].role_id,"best_choice")

    # --- 1. Separazione query / ai_query ---

    def test_query_ai_query_independence(self):
        # Con la stessa query e due ai_query diverse i candidati inviati a Gemini
        # devono avere gli stessi item_id e local_match_score.
        # user_grouping_request deve invece cambiare.
        calls=[]

        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            calls.append(payload)
            candidate_ids=[item["item_id"] for item in payload["candidates"]]
            return _gemini_two_groups(candidate_ids)

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            discover_products(self.products,"mouse",self.evidence_service,ai_query="per utilizzo")
            discover_products(self.products,"mouse",self.evidence_service,ai_query="per prezzo")

        self.assertEqual(len(calls),2)
        ids_first=[item["item_id"] for item in calls[0]["candidates"]]
        ids_second=[item["item_id"] for item in calls[1]["candidates"]]
        self.assertEqual(ids_first,ids_second)

        scores_first=[item["local_match_score"] for item in calls[0]["candidates"]]
        scores_second=[item["local_match_score"] for item in calls[1]["candidates"]]
        self.assertEqual(scores_first,scores_second)

        self.assertEqual(calls[0]["user_grouping_request"],"per utilizzo")
        self.assertEqual(calls[1]["user_grouping_request"],"per prezzo")

    # --- 2. Evidenze solo sui prodotti finali ---

    def test_evidence_only_for_final_products(self):
        # Con 4 prodotti finali nei gruppi Gemini, evidence_for_product deve essere
        # chiamata esattamente 4 volte (una per item_id unico nei gruppi).
        counting=CountingEvidenceService()

        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            candidate_ids=[item["item_id"] for item in payload["candidates"]]
            return _gemini_two_groups(candidate_ids)

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            response=discover_products(self.products,"mouse",counting,ai_query="test")

        final_ids={p.item_id for g in response.groups for p in g.products}
        self.assertEqual(len(counting.calls),len(final_ids))
        all_candidates_count=sum(
            len(g.products) for g in response.groups
        )
        self.assertLess(len(counting.calls),all_candidates_count + 1)

    def test_evidence_deduplication_same_item_id(self):
        # Se lo stesso item_id compare in piu cluster (impossibile per validazione,
        # ma il meccanismo di cache deve comunque produrre una sola chiamata).
        counting=CountingEvidenceService()

        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            ids=[item["item_id"] for item in payload["candidates"]]
            # Costruiamo manualmente due gruppi con item diversi; verifica cache.
            return json.dumps({
                "answer": "ok",
                "groups": [
                    {"cluster_id":"g1","label":"G1","description":"D1",
                     "reason":"R","item_ids":[ids[0],ids[1]]},
                    {"cluster_id":"g2","label":"G2","description":"D2",
                     "reason":"R","item_ids":[ids[2],ids[3]]},
                ],
            })

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            discover_products(self.products,"mouse",counting,ai_query="test")

        # ogni item_id deve comparire al piu una volta nelle chiamate
        self.assertEqual(len(counting.calls),len(set(counting.calls)))

    # --- 3. Nessuna local_evidence nel payload Gemini ---

    def test_no_local_evidence_in_gemini_payload(self):
        # Il payload inviato a Gemini non deve contenere il campo local_evidence.
        captured={}

        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            captured["candidates"]=payload["candidates"]
            ids=[item["item_id"] for item in payload["candidates"]]
            return _gemini_two_groups(ids)

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            discover_products(self.products,"mouse",self.evidence_service)

        for candidate in captured["candidates"]:
            self.assertNotIn("local_evidence",candidate)

    # --- 4. Fallback unico ---

    def test_fallback_single_group_structure(self):
        # Con risposta Gemini invalida il fallback produce un solo gruppo best_choice.
        with patch(
            "prototype.backend.services.discovery_service.call_gemini",
            return_value=json.dumps({"answer":"x","groups":[]}),
        ):
            response=discover_products(self.products,"mouse",self.evidence_service)

        self.assertFalse(response.used_ai_support)
        self.assertTrue(response.fallback)
        self.assertEqual(len(response.groups),1)
        self.assertEqual(response.groups[0].role_id,"best_choice")
        self.assertLessEqual(len(response.groups[0].products),MAX_GROUP_PRODUCTS)

    # --- 5. Successo Gemini ---

    def test_gemini_success_flags(self):
        # Con risposta Gemini valida used_ai_support=True e fallback=False.
        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            ids=[item["item_id"] for item in payload["candidates"]]
            return _gemini_two_groups(ids)

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            response=discover_products(self.products,"mouse",self.evidence_service)

        self.assertTrue(response.used_ai_support)
        self.assertFalse(response.fallback)

    def test_gemini_no_invented_ids_and_no_duplicates(self):
        # ID inventati scartati; nessun prodotto duplicato tra i cluster.
        def fake_gemini(prompt):
            payload=json.loads(prompt.split("Dati:\n",1)[1])
            ids=[item["item_id"] for item in payload["candidates"]]
            return json.dumps({
                "answer": "ok",
                "groups": [
                    {"cluster_id":"g1","label":"G1","description":"D1",
                     "reason":"R","item_ids":[ids[0],"INVENTATO_XYZ"]},
                    {"cluster_id":"g2","label":"G2","description":"D2",
                     "reason":"R","item_ids":[ids[1],ids[2]]},
                ],
            })

        with patch("prototype.backend.services.discovery_service.call_gemini",fake_gemini):
            response=discover_products(self.products,"mouse",self.evidence_service)

        all_ids=[p.item_id for g in response.groups for p in g.products]
        self.assertNotIn("INVENTATO_XYZ",all_ids)
        self.assertEqual(len(all_ids),len(set(all_ids)))

    # --- 6. use_ai_support=False ---

    def test_no_ai_support(self):
        # Con use_ai_support=False Gemini non deve essere chiamato.
        # Deve esserci un solo gruppo locale con fallback=True.
        with patch(
            "prototype.backend.services.discovery_service.call_gemini"
        ) as mock_gemini:
            response=discover_products(
                self.products,"mouse",self.evidence_service,use_ai_support=False
            )

        mock_gemini.assert_not_called()
        self.assertFalse(response.used_ai_support)
        self.assertTrue(response.fallback)
        self.assertEqual(len(response.groups),1)

    # --- 7. Query vuota ---

    def test_empty_query_returns_popular_products(self):
        # Query vuota: prodotti popolari, un solo gruppo, nessun errore, fallback=True.
        response=discover_products(self.products,"",self.evidence_service)

        self.assertFalse(response.used_ai_support)
        self.assertTrue(response.fallback)
        self.assertGreaterEqual(len(response.groups),1)
        self.assertIsInstance(response.answer,str)
        self.assertEqual(response.groups[0].role_id,"best_choice")

    def test_unmatched_query_returns_no_products_without_calling_gemini(self):
        with patch("prototype.backend.services.discovery_service.call_gemini") as gemini:
            response=discover_products(self.products,"zzq-demo-inesistente",self.evidence_service)

        gemini.assert_not_called()
        self.assertEqual(response.total_candidates,0)
        self.assertEqual(response.groups,[])

    def test_rare_match_is_not_padded_with_popular_products(self):
        products=self.products + [
            Product(item_id="popular",title="Garden chair",category="Garden",popularity_score=1.0),
        ]
        response=discover_products(
            products,"programmable",self.evidence_service,use_ai_support=False,
        )

        self.assertEqual(response.total_candidates,4)
        self.assertEqual({p.item_id for p in response.groups[0].products},{"p1","p3","p5","p7"})

    # --- 8. Sinonimi condivisi ---

    def test_shared_synonyms_telefono_finds_phone(self):
        # expand_query_terms("telefono") deve includere phone e smartphone.
        terms=expand_query_terms("telefono")
        self.assertIn("phone",terms)
        self.assertIn("smartphone",terms)

    def test_shared_synonyms_search_uses_query_utils(self):
        # Una ricerca con "telefono" deve trovare prodotti con "phone" o "smartphone"
        # grazie all'espansione condivisa in search_service.
        phone_products=[
            Product(
                item_id="ph1",
                title="Samsung Galaxy Smartphone",
                category="Cell Phone",
                description="Best android phone",
                price=499.0,
                average_rating=4.5,
                rating_count=200,
                popularity_score=0.9,
            )
        ]
        results=search_products(phone_products,"telefono")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].item_id,"ph1")

    def test_both_searches_require_the_requested_concepts(self):
        cases=[
            ("libri","The Hobbit","Books","Laser Printer","Font: Calibri"),
            ("libri","The Hobbit","Books","WD My Book External Hard Drive","Book series"),
            ("PlayStation","DualShock 4 for PlayStation 4","Video Games","Xbox One Controller","PlayStation comparison"),
            ("PS4","DualShock 4 for PlayStation 4","Video Games","Controller for PlayStation 3",""),
            ("mouse wireless","Wireless Computer Mouse","Electronics","Wireless Router","Mouse compatible"),
            ("stampante laser","Monochrome Laser Printer","Office Products","Labels for Laser Inkjet Printer",""),
            ("gaming","Gaming Mouse","Electronics","Wireless Router","Gaming"),
            ("cover iphone 5","Case for iPhone 5","Electronics","Case for iPhone 5C",""),
            ("TP-Link","TP-Link Wireless Router","Electronics","Automatic Cat Feeder","Works with TP-Link outlet"),
            ("filtro","Vacuum Filter Pack","Home and Kitchen","Replacement Keyboard",""),
        ]
        for query,title,category,noise,description in cases:
            with self.subTest(query=query,noise=noise):
                products=[
                    Product(item_id="match",title=title,category=category),
                    Product(item_id="noise",title=noise,category="Electronics",
                            description=description,popularity_score=1.0),
                ]
                self.assertEqual([p.item_id for p in search_products(products,query)],["match"])
                response=discover_products(products,query,self.evidence_service,use_ai_support=False)
                self.assertEqual(response.total_candidates,1)
                self.assertEqual([p.item_id for g in response.groups for p in g.products],["match"])

    def test_mouse_complements_use_a_separate_keyboard(self):
        products=[
            Product(item_id=item_id,title=title,category="Electronics",image_url="https://example.org/product.png")
            for item_id,title in [
                ("mouse","Logitech Wireless Mouse"),
                ("keyboard","Logitech Wireless Keyboard"),
                ("combo","Logitech Wireless Keyboard and Mouse Bundle"),
            ]
        ]
        response=contextual_recommendations(products,"mouse",self.evidence_service,use_ai_support=False)
        complements=[p.item_id for g in response.groups if g.role_id=="complementary" for p in g.products]
        self.assertEqual(complements,["keyboard"])


if __name__ == "__main__":
    unittest.main()
