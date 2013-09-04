from pyramid.view import view_config 
from pyramid.view import view_defaults
from pyramid.exceptions import HTTPNotFound
from pyramid.response import Response
from lbgenerator.model import begin_session
from lbgenerator.model import base_exists
from lbgenerator.model import reg_hyper_class 
from lbgenerator.model import doc_hyper_class
from lbgenerator.lib import utils
import json
import datetime

@view_config(route_name='download')
def download(request):
    session = begin_session()

    # Route: api/doc/{base_name}/{id_doc}/download
    base_name = request.matchdict.get('base_name')
    id_doc = request.matchdict.get('id_doc')

    # Get hyper class
    DocHyperClass = doc_hyper_class(base_name)

    # Query the object
    doc = session.query(DocHyperClass).filter_by(id_doc = id_doc).first()
    session.close()
    if doc is None:
        raise HTTPNotFound()

    cd = 'filename=' + doc.nome_doc

    params = request.params
    if params.get('disposition'):
        if params['disposition'] == 'attachment':
            cd = 'attachment;' + cd
        elif params['disposition'] == 'inline':
            cd = 'inline;' + cd

    # make the response object
    return Response(
        content_type=doc.mimetype, 
        content_disposition=cd, 
        app_iter=[doc.blob_doc]
    )

    return response

@view_config(route_name='full_reg')
def full_reg(request, json_reg=None):

    session = begin_session()
    base_name = request.matchdict.get('base_name')
    if not base_exists(base_name):
        raise Exception('Base does not exist!')
    id_reg = request.matchdict.get('id_reg')

    RegHyperClass = reg_hyper_class(base_name)
    DocHyperClass = doc_hyper_class(base_name)

    doc_texts = dict()
    doc_cols = (
               DocHyperClass.id_doc,
               DocHyperClass.texto_doc,
               DocHyperClass.grupos_acesso,
               DocHyperClass.dt_ext_texto
               )

    query = session.query(*doc_cols).filter_by(id_reg = id_reg).all()
    if query:
        for q in query:
            doc_texts[q.id_doc] = dict(
                                      texto_doc = q.texto_doc,
                                      grupos_acesso = q.grupos_acesso,
                                      dt_ext_texto = str(q.dt_ext_texto)
                                      )

    if json_reg:
        jr = utils.to_json(json_reg)
    else:
        query = session.query(RegHyperClass.json_reg).filter_by(id_reg = id_reg).first()
        session.close()

        if query is None: raise HTTPNotFound()
        else: query = query[0]
        jr = utils.to_json(query)

    doc_ids = list()
    for k, v in jr.items():
        if type(v) is dict and 'id_doc' in v:
            if v['id_doc'] in doc_texts:
                v.update(doc_texts[v['id_doc']])

    dump = json.dumps(jr)
    return Response(dump, content_type='application/json')

@view_defaults(route_name='text')
class DocText(object):

    def __init__(self, request):
        self.request = request
        self.base_name = request.matchdict.get('base_name')
        self.id_doc = request.matchdict.get('id_doc')
        if not base_exists(self.base_name):
            raise Exception('Base does not exist!')
        self.doc_entity = doc_hyper_class(self.base_name)
        self.reg_entity = reg_hyper_class(self.base_name)
        self.session = begin_session()

    def get_text(self, id_doc):
        response = self.session.query(self.doc_entity.texto_doc).filter_by(id_doc=id_doc).first()
        if response is None:
            raise HTTPNotFound()
        self.session.close()
        return response[0]

    @view_config(request_method='GET')
    def get(self):
        text = self.get_text(self.id_doc)
        response = {'texto_doc': text}
        return Response(json.dumps(response, ensure_ascii=True), content_type='application/json')

    @view_config(request_method='POST')
    def post(self):
        params = self.request.params
        if not 'texto_doc' in params:
            raise Exception('Required param: texto_doc')

        doc = self.session.query(self.doc_entity).get(self.id_doc)
        if not doc:
            raise HTTPNotFound()

        reg = self.session.query(self.reg_entity).get(doc.id_reg)
        if not reg:
            raise HTTPNotFound()

        text = params.get('texto_doc')
        doc.texto_doc = text
        doc.dt_ext_texto = str(datetime.datetime.now())
        if text != 'nulo':
            reg.dt_index_tex = None

        self.session.commit()
        self.session.close()
        return Response('UPDATED', content_type='application/json')



