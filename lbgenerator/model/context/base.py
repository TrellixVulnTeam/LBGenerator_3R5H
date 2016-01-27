import datetime
import logging

from sqlalchemy.util import KeyedTuple

from . import CustomContextFactory
from ..entities import *
from ..index import Index
from ... import model
from ... import config
from ...lib import utils
from sqlalchemy.util import KeyedTuple
import requests

log = logging.getLogger()


class BaseContextFactory(CustomContextFactory):
    
        # Restarta o lbindex quando a base for modificada
    def lbirestart(self):
        param = {'directive': 'restart'}
        url = config.LBI_URL
        response = requests.post(url, param)
        if response.status_code != 200:
            raise Exception('Error %s to restart LBIndex'
                % response.status_code ,requests.exceptions.RequestException)

    """ Base Factory Methods
    """

    entity = LBBase

    def get_next_id(self):
        return model.base_next_id()

    def get_member(self, base):
        self.single_member = True
        member = self.session.query(self.entity)\
            .filter_by(name=base).first()
        return member or None

    def create_member(self, data):

        # Create reg and doc tables.
        base_name = data['name']
        base_json = utils.json2object(data['struct'])

        '''
        Trata-se de uma variável global de __init__.py
        global BASES
        BASES = BaseMemory(begin_session, LBBase)
        '''
        base = model.BASES.set_base(base_json)
        data['struct'] = base.json
        data['txt_mapping'] = base.txt_mapping_json

        file_table = get_file_table(base_name, config.METADATA)
        doc_table = get_doc_table(base_name, config.METADATA,
            **base.relational_fields)
        file_table.create(config.ENGINE, checkfirst=True)
        doc_table.create(config.ENGINE, checkfirst=True)

        member = self.entity(**data)
        self.session.add(member)
        self.session.commit()
        self.session.close()
        self.lbirestart()
        return member

    def update_member(self, id, data):
        member = self.get_member(id)
        if member is None:
            return None

        if member.name != data['name']:
            old_name = 'lb_doc_%s' %(member.name)
            new_name = 'lb_doc_%s' %(data['name'])
            self.session.execute('ALTER TABLE %s RENAME TO %s' %(old_name, new_name))

            old_name = 'lb_file_%s' %(member.name)
            new_name = 'lb_file_%s' %(data['name'])
            self.session.execute('ALTER TABLE %s RENAME TO %s' %(old_name, new_name))

            old_name = 'lb_doc_%s_id_doc_seq' %(member.name)
            new_name = 'lb_doc_%s_id_doc_seq' %(data['name'])
            self.session.execute('ALTER SEQUENCE %s RENAME TO %s' %(old_name, new_name))

            old_name = 'lb_file_%s_id_file_seq' %(member.name)
            new_name = 'lb_file_%s_id_file_seq' %(data['name'])
            self.session.execute('ALTER SEQUENCE %s RENAME TO %s' %(old_name, new_name))

        for name in data:
            setattr(member, name, data[name])

        self.session.commit()

        model.HISTORY.create_member(**{
            'id_base': member.id_base,
            'author': 'Author',
            'date': datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'name': member.name,
            'structure': utils.json2object(member.struct),
            'status': 'UPDATED'
        })
        self.lbirestart()
        self.session.close()

        return member

    def delete_member(self, id):
        member = self.get_member(id)
        if member is None:
            return None

        index = None
        relational_fields = model.BASES.get_base(member.name).relational_fields
        if model.BASES.bases.get(member.name) is not None:
            index = Index(model.BASES.bases[member.name], None)
            del model.BASES.bases[member.name]

        # Delete parallel tables.
        file_table = get_file_table(member.name, config.METADATA)
        doc_table = get_doc_table(member.name, config.METADATA, **relational_fields)
        file_table.drop(config.ENGINE, checkfirst=True)
        doc_table.drop(config.ENGINE, checkfirst=True)

        # Delete base.
        self.session.delete(member)
        self.session.commit()
        if index:
            index.delete_root()

        model.HISTORY.create_member(**{
            'id_base': member.id_base,
            'author': 'Author',
            'date': datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'name': member.name,
            'structure': utils.json2object(member.struct),
            'status': 'DELETE'
        })
        self.lbirestart()
        self.session.close()
        return member

    def member_to_dict(self, member, fields=None):

        '''
        TODO: Não consegui entender pq o sempre verifica se há o método 
        "_asdict()" visto que ele nunca está disponível e o pior de tudo 
        é que sempre loga. Tá tosco no último e por essa razão comentei 
        a linha que gera o log! By Questor
        '''
        try:
            dict_member = member._asdict()
        except AttributeError as e:
            # Continue parsing.
            if not isinstance(member, KeyedTuple):
                member = self.member2KeyedTuple(member)

        dict_member = utils.json2object(member._asdict()['struct'])

        fields = getattr(self,'_query', {}).get('select')
        if fields and not '*' in fields:
            return {'metadata':
                {field: dict_member['metadata'][field] for field in fields}
            }

        return dict_member
