import requests
import getpass

class Metabase_API():
  
  def __init__(self, domain, email, password=None, basic_auth=False):
    
    self.domain = domain.rstrip('/')
    self.email = email
    self.password = getpass.getpass(prompt='Please enter your password: ') if password is None else password
    self.session_id = None
    self.header = None
    self.auth = (self.email, self.password) if basic_auth else None
    self.authenticate()
  
  
  def authenticate(self):
    """Get a Session ID"""
    conn_header = {'username':self.email,
                   'password':self.password}

    res = requests.post(self.domain + '/api/session', json=conn_header, auth=self.auth)
    if not res.ok:
      raise Exception(res)
    
    self.session_id = res.json()['id']
    self.header = {'X-Metabase-Session':self.session_id}
  
  
  def validate_session(self):
    """Get a new session ID if the previous one has expired"""
    res = requests.get(self.domain + '/api/user/current', headers=self.header, auth=self.auth)
    
    if res.ok:  # 200
      return True
    elif res.status_code == 401:  # unauthorized
      return self.authenticate()
    else:
      raise Exception(res)
  
  
  
  ##################################################################
  ######################### REST Methods ###########################
  ##################################################################
  
  def get(self, endpoint, *args, **kwargs):
    self.validate_session()
    res = requests.get(self.domain + endpoint, headers=self.header, **kwargs, auth=self.auth)
    if 'raw' in args:
      return res
    else:
      return res.json() if res.ok else False
  
  
  def post(self, endpoint, *args, **kwargs):
    self.validate_session()
    res = requests.post(self.domain + endpoint, headers=self.header, **kwargs, auth=self.auth)
    if 'raw' in args:
      return res
    else:
      return res.json() if res.ok else False
  
  
  def put(self, endpoint, *args, **kwargs):
    """Used for updating objects (cards, dashboards, ...)"""
    self.validate_session()
    res = requests.put(self.domain + endpoint, headers=self.header, **kwargs, auth=self.auth)
    if 'raw' in args:
      return res
    else:
      return res.status_code
  
  
  def delete(self, endpoint, *args, **kwargs):
    self.validate_session()
    res = requests.delete(self.domain + endpoint, headers=self.header, **kwargs, auth=self.auth)
    if 'raw' in args:
      return res
    else:
      return res.status_code
  
  
  
  ##################################################################
  ##################### Auxiliary Functions ########################
  ##################################################################
  
  def get_item_name(self, item_type, item_id):
    
    assert item_type in ['card', 'table', 'dashboard', 'collection', 'pulse']

    res = self.get("/api/{}/{}".format(item_type, item_id))
    if res:
      return res['name']
    else:
      raise ValueError('There is no {} with the id {}'.format(item_type, item_id))
  

  
  def get_item_id(self, item_type, item_name, collection_id=None, collection_name=None):
    
    assert item_type in ['card', 'dashboard', 'pulse']

    if not collection_id:
      if not collection_name:
        # Collection name/id is not provided. Searching in all collections 
        item_IDs = [ i['id'] for i in self.get("/api/{}/".format(item_type)) if i['name'] == item_name 
                                                                            and i['archived'] == False ]
      else:
        collection_id = self.get_collection_id(collection_name) if collection_name != 'root' else None
        item_IDs = [ i['id'] for i in self.get("/api/{}/".format(item_type)) if i['name'] == item_name 
                                                                            and i['collection_id'] == collection_id 
                                                                            and i['archived'] == False ]
    else:
      collection_name = self.get_item_name('collection', collection_id)
      item_IDs = [ i['id'] for i in self.get("/api/{}/".format(item_type)) if i['name'] == item_name 
                                                                          and i['collection_id'] == collection_id 
                                                                          and i['archived'] == False ]
    
    if len(item_IDs) > 1:
      if not collection_name:
        raise ValueError('There is more than one {} with the name "{}".\n\
            Provide collection id/name to limit the search space'.format(item_type, item_name))
      raise ValueError('There is more than one {} with the name "{}" in the collection "{}"'
                       .format(item_type, item_name, collection_name))
    if len(item_IDs) == 0:
      if not collection_name:
          raise ValueError('There is no {} with the name "{}"'.format(item_type, item_name))
      raise ValueError('There is no item with the name "{}" in the collection "{}"'
                       .format(item_name, collection_name))
    
    return item_IDs[0] 
  

  
  def get_collection_id(self, collection_name):
    collection_IDs = [ i['id'] for i in self.get("/api/collection/") if i['name'] == collection_name ]
    
    if len(collection_IDs) > 1:
      raise ValueError('There is more than one collection with the name {}'.format(collection_name))
    if len(collection_IDs) == 0:
      raise ValueError('There is no collection with the name "{}"'.format(collection_name))
    
    return collection_IDs[0] 


  
  def get_segment_id(self, segment_name, table_id=None):
    segment_IDs = [ i['id'] for i in self.get("/api/segment/") if i['name'] == segment_name 
                                                              and (not table_id or i['table_id'] == table_id) ]
    if len(segment_IDs) > 1:
      raise ValueError('There is more than one segment with the name {}'.format(segment_name))
    if len(segment_IDs) == 0:
      raise ValueError('There is no segment with the name "{}"'.format(segment_name))
    
    return segment_IDs[0]



  def get_db_id(self, db_name):
    res = self.get("/api/database/")
    if type(res) == dict:  # in Metabase version *.40.0 the format of the returned result for this endpoint changed
      res = res['data']
    db_IDs = [ i['id'] for i in res if i['name'] == db_name ]
    
    if len(db_IDs) > 1:
      raise ValueError('There is more than one DB with the name {}'.format(db_name))
    if len(db_IDs) == 0:
      raise ValueError('There is no DB with the name "{}"'.format(db_name))
    
    return db_IDs[0]
  

  
  def get_table_id(self, table_name, table_schema=None, table_dataset=None, db_name=None, db_id=None):
    tables = self.get("/api/table/")

    if table_schema and table_dataset:
        raise ValueError('There cannot be both table schema and table dataset id values. Please specify either one of the above')
    else:
      if db_id and db_name and table_schema:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['id'] == db_id
                       and i['db']['name'] == db_name
                       and i['schema'] == table_schema]
      elif db_id and db_name and table_dataset:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['id'] == db_id
                       and i['db']['name'] == db_name
                       and i['schema'] == table_schema
                       and 'dataset-id' in i['db']['details']
                       and i['db']['details']['dataset-id'] == table_dataset]
      elif db_id and db_name:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['id'] == db_id
                       and i['db']['name'] == db_name]
      elif db_name and table_schema:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['name'] == db_name
                       and i['schema'] == table_schema]
      elif db_name and table_dataset:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['name'] == db_name
                       and i['schema'] == table_schema
                       and 'dataset-id' in i['db']['details']
                       and i['db']['details']['dataset-id'] == table_dataset]
      elif db_id and table_schema:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['id'] == db_id
                       and i['schema'] == table_schema]
      elif db_id and table_dataset:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and i['db']['id'] == db_id
                       and i['schema'] == table_schema
                       and 'dataset-id' in i['db']['details']
                       and i['db']['details']['dataset-id'] == table_dataset]
      elif db_id:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name and i['db']['id'] == db_id]
      elif db_name:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name and i['db']['name'] == db_name]
      elif table_schema:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name and i['schema'] == table_schema]
      elif table_dataset:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name
                       and 'dataset-id' in i['db']['details']
                       and i['db']['details']['dataset-id'] == table_dataset]
      else:
          table_IDs = [i['id'] for i in tables if i['name'] == table_name]

      if len(table_IDs) > 1:
          raise ValueError('There is more than one table with the name {}. Provide db id/name and/or table schema/dataset.'.format(table_name))
      if len(table_IDs) == 0:
          raise ValueError('There is no table with the name "{}" (in the provided db, if any)'.format(table_name))

      return table_IDs[0]


  def get_db_id_from_table_id(self, table_id):
    tables = [ i['db_id'] for i in self.get("/api/table/") if i['id'] == table_id ]
    
    if len(tables) == 0:
      raise ValueError('There is no DB containing the table with the ID {}'.format(table_id))
    
    return tables[0]



  def get_db_info(self, db_name=None, db_id=None, params=None):
    '''
    Return Database info. Use 'params' for providing arguments.
    For example to include tables in the result, use: params={'include':'tables'}
    '''
    if params:
      assert type(params) == dict

    if not db_id:
      if not db_name:
        raise ValueError('Either the name or id of the DB needs to be provided.')
      db_id = self.get_db_id(db_name=db_name)
      
    return self.get("/api/database/{}".format(db_id), params=params)

  def get_table_metadata(self, table_name=None, table_schema=None, table_dataset=None, table_id=None, db_name=None, db_id=None,
                         params=None):
    if params:
      assert type(params) == dict

    if not table_id:
      if not table_name:
        raise ValueError('Either the name or id of the table needs to be provided.')
      table_id = self.get_table_id(table_name=table_name, table_schema=table_schema, table_dataset=table_dataset,
                                   db_name=db_name, db_id=db_id)

    return self.get("/api/table/{}/query_metadata".format(table_id), params=params)


  def get_columns_name_id(self, table_name=None, db_name=None, table_id=None, db_id=None, verbose=False, column_id_name=False):
    '''Return a dictionary with col_name key and col_id value, for the given table_id/table_name in the given db_id/db_name.
       If column_id_name is True, return a dictionary with col_id key and col_name value.
    '''
    if not self.friendly_names_is_disabled():
      raise ValueError('Please disable "Friendly Table and Field Names" from Admin Panel > Settings > General, and try again.')

    if not table_name:
      if not table_id:
        raise ValueError('Either the name or id of the table must be provided.')
      table_name = self.get_item_name(item_type='table', item_id=table_id)

    # getting db_id
    if not db_id:
      if db_name:
        db_id = self.get_db_id(db_name)
      else:
        if not table_id:
          table_id = self.get_table_id(table_name)
        db_id = self.get_db_id_from_table_id(table_id)
        
    # Getting column names and IDs 
    if column_id_name:
      return {i['id']: i['name'] for i in self.get("/api/database/{}/fields".format(db_id)) 
                                 if i['table_name'] == table_name}
    else:
      return {i['name']: i['id'] for i in self.get("/api/database/{}/fields".format(db_id)) 
                                 if i['table_name'] == table_name}



  def friendly_names_is_disabled(self):
    '''
    The endpoint /api/database/:db-id/fields which is used in the function get_column_name_id relies on the display name of fields. 
    If "Friendly Table and Field Names" (in Admin Panel > Settings > General) is not disabled, it changes the display name of fields.
    So it is important to make sure this setting is disabled, before running the get_column_name_id function.
    '''
    friendly_name_setting = [ i['value'] for i in self.get('/api/setting') if i['key'] == 'humanization-strategy' ][0]
    return friendly_name_setting == 'none'  # 'none' means disabled



  @staticmethod
  def verbose_print(verbose, msg):
    if verbose:
      print(msg)
  
  
  
  ##################################################################
  ###################### Custom Functions ##########################
  ##################################################################
  
  def create_card(self, card_name=None, collection_name=None, collection_id=None, 
                  db_name=None, db_id=None, table_name=None,  table_id=None, 
                  column_order='db_table_order', custom_json=None, verbose=False, return_card=False):
    """
    Create a card using the given arguments utilizing the endpoint 'POST /api/card/'. 
    If collection is not given, the root collection is used.
    
    Keyword arguments:
    card_name -- the name used to create the card (default None) 
    collection_name -- name of the collection to place the card (default None).
    collection_id -- id of the collection to place the card (default None) 
    db_name -- name of the db that is used as the source of data (default None)  
    db_id -- id of the db used as the source of data (default None) 
    table_name -- name of the table used as the source of data (default None)
    table_id -- id of the table used as the source of data (default None) 
    column_order -- order for showing columns. Accepted values are 'alphabetical', 'db_table_order' (default) 
                    or a list of column names
    custom_json -- key-value pairs that can provide some or all the data needed for creating the card (default None).
                   If you are providing only this argument, the keys 'name', 'dataset_query' and 'display' are required
                   (https://github.com/metabase/metabase/blob/master/docs/api-documentation.md#post-apicard).
                   Although the key 'visualization_settings' is required for the endpoint, but since it can be an 
                   empty dict ({}), if it is absent in the provided json, the function adds it automatically. 
    verbose -- whether to print extra information (default False)
    return_card --  whather to return the created card info (default False)
    """
    if custom_json:
      assert type(custom_json) == dict
      # checking whether the provided json has the required info or not
      complete_json = True
      for item in ['name', 'dataset_query', 'display']:
        if item not in custom_json:
          complete_json = False
          self.verbose_print(verbose, 'The provided json is detected as partial.')
          break
      
      # Fix for the issue #10
      if custom_json.get('description') == '': 
        custom_json['description'] = None

      # setting the collection
      if collection_id:
        custom_json['collection_id'] = collection_id
      elif collection_name:
        collection_id = self.get_collection_id(collection_name)
        custom_json['collection_id'] = collection_id

      if complete_json:
        # Adding visualization_settings if it is not present in the custom_json
        if 'visualization_settings' not in custom_json:
          custom_json['visualization_settings'] = {}
        # adding the card name if it is provided
        if card_name is not None:
          custom_json['name'] = card_name
        if not custom_json.get('collection_id'):
          self.verbose_print(verbose, 'No collection name or id is provided. Will create the card at the root ...')
          
        # Creating the card using only the provided custom_json 
        res = self.post("/api/card/", json=custom_json)
        if res and not res.get('error'):
          self.verbose_print(verbose, 'The card was created successfully.')
          return res if return_card else None
        else:
          print('Card Creation Failed.\n', res)
          return res
    
    # making sure we have the required data
    if not card_name and (not custom_json or not custom_json.get('name')):
      raise ValueError("A name must be provided for the card (either as card_name argument or as part of the custom_json ('name' key)).")
    if not table_id:
      if not table_name:
        raise ValueError('Either the name or id of the table must be provided.')
      table_id = self.get_table_id(table_name=table_name, db_id=db_id, db_name=db_name)
    if not table_name:
      table_name = self.get_item_name(item_type='table', item_id=table_id)
    if not db_id:
      db_id = self.get_db_id_from_table_id(table_id)

    # getting collection_id if it is not given
    if not collection_id:
      if not collection_name:
        self.verbose_print(verbose, 'No collection name or id is provided. Will create the card at the root ...')
      else:
        collection_id = self.get_collection_id(collection_name)
    
    if type(column_order) == list:

      column_name_id_dict = self.get_columns_name_id(db_id=db_id, 
                                                     table_id=table_id, 
                                                     table_name=table_name, 
                                                     verbose=verbose)
      try:
        column_id_list = [column_name_id_dict[i] for i in column_order]
      except ValueError as e:
        print('The column name {} is not in the table {}. \nThe card creation failed!'.format(e, table_name))
        return False

      column_id_list_str = [['field-id', i] for i in column_id_list]

    elif column_order == 'db_table_order':  # default

      ### Finding the actual order of columns in the table as they appear in the database
      # creating a temporary card for retrieving column ordering
      json_str = """{{'dataset_query': {{'database': {1},
                                    'native': {{'query': 'SELECT * from "{2}";' }},
                                    'type': 'native' }},
              'display': 'table',
              'name': '{0}',
              'visualization_settings': {{}} }}""".format(card_name, db_id, table_name)
      
      res = self.post("/api/card/", json=eval(json_str))  
      if not res:
        print('Card Creation Failed!')
        return res
      ordered_columns = [ i['name'] for i in res['result_metadata'] ]  # retrieving the column ordering

      # deleting the temporary card
      card_id = res['id']
      self.delete("/api/card/{}".format(card_id))  

      column_name_id_dict = self.get_columns_name_id(db_id=db_id, 
                                                     table_id=table_id, 
                                                     table_name=table_name, 
                                                     verbose=verbose)
      column_id_list = [ column_name_id_dict[i] for i in ordered_columns ]
      column_id_list_str = [ ['field-id', i] for i in column_id_list ]
    
    elif column_order == 'alphabetical':
      column_id_list_str = None
    
    else:
      raise ValueError("Wrong value for 'column_order'. \
                       Accepted values: 'alphabetical', 'db_table_order' or a list of column names.")
    
    # default json
    json_str = """{{'dataset_query': {{'database': {1},
                                      'query': {{'fields': {4},
                                                 'source-table': {2}}},
                                      'type': 'query'}},
                   'display': 'table',
                   'name': '{0}',
                   'collection_id': {3},
                   'visualization_settings': {{}}
                   }}""".format(card_name, db_id, table_id, collection_id, column_id_list_str)
    json = eval(json_str)
    
    # adding/rewriting data to the default json from custom_json
    if custom_json:
      for key, value in custom_json.items():
        if key in ['name', 'dataset_query', 'display']:
          self.verbose_print(verbose, "Ignored '{}' key in the provided custom_json.".format(key))
          continue
        json[key] = value
    
    res = self.post("/api/card/", json=json)
    
    # getting collection_name to be used in the final message
    if not collection_name:
      if not collection_id:
        collection_name = 'root'
      else:
        collection_name = self.get_item_name(item_type='collection', item_id=collection_id)
    
    if res and not res.get('error'):
      self.verbose_print(verbose, "The card '{}' was created successfully in the collection '{}'."
                         .format(card_name, collection_name))
      if return_card: return res
    else:
      print('Card Creation Failed.\n', res)
      return res
  

  
  def create_collection(self, collection_name, parent_collection_id=None, parent_collection_name=None, return_results=False):
    """
    Create an empty collection, in the given location, utilizing the endpoint 'POST /api/collection/'. 
    
    Keyword arguments:
    collection_name -- the name used for the created collection.
    parent_collection_id -- id of the collection where the created collection resides in.
    parent_collection_name -- name of the collection where the created collection resides in (use 'Root' for the root collection).
    return_results -- whether to return the resuls or not.
    """
    # making sure we have the data we need
    if not parent_collection_id:
      if not parent_collection_name:
        print('Either the name of id of the parent collection must be provided.')
      if parent_collection_name == 'Root':
        parent_collection_id = None
      else:
        parent_collection_id = self.get_collection_id(parent_collection_name)
    
    res = self.post('/api/collection', json={'name':collection_name, 'parent_id':parent_collection_id, 'color':'#509EE3'})
    if return_results:
      return res



  def create_segment(self, segment_name, column_name, column_values, segment_description='', 
                     db_name=None, db_id=None, table_name=None, table_id=None, return_segment=False):
    """
    Create a segment using the given arguments utilizing the endpoint 'POST /api/segment/'. 
    
    Keyword arguments:
    segment_name -- the name used for the created segment.
    column_name -- name of the column used for filtering.
    column_values -- list of values for filtering in the given column.
    segment_description -- description of the segment (default '') 
    db_name -- name of the db that is used as the source of data (default None)  
    db_id -- id of the db used as the source of data (default None) 
    table_name -- name of the table used for creating the segmnet on it (default None)  
    table_id -- id of the table used for creating the segmnet on it (default None)  
    return_segment --  whather to return the created segment info (default False)
    """
    # making sure we have the data needed
    if not table_name and not table_id:
      raise ValueError('Either the name or id of the table must be provided.')
    if not table_id:
      table_id = self.get_table_id(table_name, db_name, db_id)
    if not table_name:
      table_name = self.get_item_name(item_type='table', item_id=table_id)
    db_id = self.get_db_id_from_table_id(table_id)

    colmuns_name_id_mapping = self.get_columns_name_id(table_name=table_name, db_id=db_id)
    column_id = colmuns_name_id_mapping[column_name]
    
    # creating a segment blueprint
    segment_blueprint = {'name': segment_name,
                         'description': segment_description,
                         'table_id': table_id,
                         'definition': {'source-table': table_id, 'filter': ['=', ['field-id', column_id]]}}
    
    # adding filtering values
    segment_blueprint['definition']['filter'].extend(column_values)
    
    # creating the segment
    res = self.post('/api/segment/', json=segment_blueprint)
    if return_segment:
      return res



  def copy_card(self, source_card_name=None, source_card_id=None, 
                source_collection_name=None, source_collection_id=None,
                destination_card_name=None, 
                destination_collection_name=None, destination_collection_id=None,
                postfix='', verbose=False):
    """
    Copy the card with the given name/id to the given destination collection. 
    
    Keyword arguments:
    source_card_name -- name of the card to copy (default None) 
    source_card_id -- id of the card to copy (default None) 
    source_collection_name -- name of the collection the source card is located in (default None) 
    source_collection_id -- id of the collection the source card is located in (default None) 
    destination_card_name -- name used for the card in destination (default None).
                             If None, it will use the name of the source card + postfix.
    destination_collection_name -- name of the collection to copy the card to (default None) 
    destination_collection_id -- id of the collection to copy the card to (default None) 
    postfix -- if destination_card_name is None, adds this string to the end of source_card_name 
               to make destination_card_name
    """
    ### Making sure we have the data that we need 
    if not source_card_id:
      if not source_card_name:
        raise ValueError('Either the name or id of the source card must be provided.')
      else:
        source_card_id = self.get_item_id(item_type='card',
                                          item_name=source_card_name, 
                                          collection_id=source_collection_id, 
                                          collection_name=source_collection_name)
    
    if not destination_collection_id:
      if not destination_collection_name:
        raise ValueError('Either the name or id of the destination collection must be provided.')
      else:
        destination_collection_id = self.get_collection_id(destination_collection_name)
    
    if not destination_card_name:
      if not source_card_name:
        source_card_name = self.get_item_name(item_type='card', item_id=source_card_id)
      destination_card_name = source_card_name + postfix
      
    # Getting the source card info
    source_card = self.get('/api/card/{}'.format(source_card_id))
    
    # Updating the name and collection_id
    card_json = source_card
    card_json['collection_id'] = destination_collection_id
    card_json['name'] = destination_card_name
    
    # Fixing the issue #10
    if card_json.get('description') == '': 
      card_json['description'] = None

    # saving as a new card
    res = self.create_card(custom_json=card_json, verbose=verbose, return_card=True)
    
    # returning the id of the created card
    return res['id']



  def copy_pulse(self, source_pulse_name=None, source_pulse_id=None, 
                 source_collection_name=None, source_collection_id=None,
                 destination_pulse_name=None, 
                 destination_collection_id=None, destination_collection_name=None, postfix=''):
    """
    Copy the pulse with the given name/id to the given destination collection. 
    
    Keyword arguments:
    source_pulse_name -- name of the pulse to copy (default None) 
    source_pulse_id -- id of the pulse to copy (default None) 
    source_collection_name -- name of the collection the source card is located in (default None) 
    source_collection_id -- id of the collection the source card is located in (default None) 
    destination_pulse_name -- name used for the pulse in destination (default None).
                             If None, it will use the name of the source pulse + postfix.
    destination_collection_name -- name of the collection to copy the pulse to (default None) 
    destination_collection_id -- id of the collection to copy the pulse to (default None) 
    postfix -- if destination_pulse_name is None, adds this string to the end of source_pulse_name 
               to make destination_pulse_name
    """
    ### Making sure we have the data that we need 
    if not source_pulse_id:
      if not source_pulse_name:
        raise ValueError('Either the name or id of the source pulse must be provided.')
      else:
        source_pulse_id = self.get_item_id(item_type='pulse',item_name=source_pulse_name, 
                                           collection_id=source_collection_id, 
                                           collection_name=source_collection_name)
    
    if not destination_collection_id:
      if not destination_collection_name:
        raise ValueError('Either the name or id of the destination collection must be provided.')
      else:
        destination_collection_id = self.get_collection_id(destination_collection_name)
    
    if not destination_pulse_name:
      if not source_pulse_name:
        source_pulse_name = self.get_item_name(item_type='pulse', item_id=source_pulse_id)
      destination_pulse_name = source_pulse_name + postfix
  
    # Getting the source pulse info
    source_pulse = self.get('/api/pulse/{}'.format(source_pulse_id))
    
    # Updating the name and collection_id
    pulse_json = source_pulse
    pulse_json['collection_id'] = destination_collection_id
    pulse_json['name'] = destination_pulse_name
    
    # saving as a new pulse
    self.post('/api/pulse', json=pulse_json)
    
  

  def copy_dashboard(self, source_dashboard_name=None, source_dashboard_id=None, 
                     source_collection_name=None, source_collection_id=None,
                     destination_dashboard_name=None, 
                     destination_collection_name=None, destination_collection_id=None,
                     deepcopy=False, postfix=''):
    """
    Copy the dashboard with the given name/id to the given destination collection. 
    
    Keyword arguments:
    source_dashboard_name -- name of the dashboard to copy (default None) 
    source_dashboard_id -- id of the dashboard to copy (default None) 
    source_collection_name -- name of the collection the source dashboard is located in (default None) 
    source_collection_id -- id of the collection the source dashboard is located in (default None) 
    destination_dashboard_name -- name used for the dashboard in destination (default None).
                                  If None, it will use the name of the source dashboard + postfix.
    destination_collection_name -- name of the collection to copy the dashboard to (default None) 
    destination_collection_id -- id of the collection to copy the dashboard to (default None) 
    deepcopy -- whether to duplicate the cards inside the dashboard (default False).
                If True, puts the duplicated cards in a collection called "[dashboard_name]'s duplicated cards" 
                in the same path as the duplicated dashboard.
    postfix -- if destination_dashboard_name is None, adds this string to the end of source_dashboard_name 
               to make destination_dashboard_name
    """
    ### Making sure we have the data that we need 
    if not source_dashboard_id:
      if not source_dashboard_name:
        raise ValueError('Either the name or id of the source dashboard must be provided.')
      else:
        source_dashboard_id = self.get_item_id(item_type='dashboard',item_name=source_dashboard_name, 
                                               collection_id=source_collection_id, 
                                               collection_name=source_collection_name)
    
    if not destination_collection_id:
      if not destination_collection_name:
        raise ValueError('Either the name or id of the destination collection must be provided.')
      else:
        destination_collection_id = self.get_collection_id(destination_collection_name)
    
    if not destination_dashboard_name:
      if not source_dashboard_name:
        source_dashboard_name = self.get_item_name(item_type='dashboard', item_id=source_dashboard_id)
      destination_dashboard_name = source_dashboard_name + postfix

    ### shallow-copy
    shallow_copy_json = {'collection_id':destination_collection_id, 'name':destination_dashboard_name}
    res = self.post('/api/dashboard/{}/copy'.format(source_dashboard_id), json=shallow_copy_json)
    dup_dashboard_id = res['id']
    
    ### deepcopy
    if deepcopy:
      # Getting the source dashboard info
      source_dashboard = self.get('/api/dashboard/{}'.format(source_dashboard_id))
      
      # creating an empty collection to copy the cards into it
      res = self.post('/api/collection/', 
                      json={'name':destination_dashboard_name + "'s cards", 
                            'color':'#509EE3', 
                            'parent_id':destination_collection_id})
      cards_collection_id = res['id']

      # duplicating cards and putting them in the created collection and making a card_id mapping
      source_dashboard_card_IDs = [ i['card_id'] for i in source_dashboard['ordered_cards'] if i['card_id'] is not None ]
      card_id_mapping = {}
      for card_id in source_dashboard_card_IDs:
        dup_card_id = self.copy_card(source_card_id=card_id, destination_collection_id=cards_collection_id)
        card_id_mapping[card_id] = dup_card_id

      # replacing cards in the duplicated dashboard with duplicated cards
      dup_dashboard = self.get('/api/dashboard/{}'.format(dup_dashboard_id))
      for card in dup_dashboard['ordered_cards']:
        
        # ignoring text boxes. These get copied in the shallow-copy stage.
        if card['card_id'] is None:
          continue
          
        # preparing a json to be used for replacing the cards in the duplicated dashboard
        new_card_id = card_id_mapping[card['card_id']]
        card_json = {}
        card_json['cardId'] = new_card_id
        for prop in ['visualization_settings', 'col', 'row', 'sizeX', 'sizeY', 'series', 'parameter_mappings']:
          card_json[prop] = card[prop]
        for item in card_json['parameter_mappings']:
          item['card_id'] = new_card_id
        # removing the card from the duplicated dashboard
        dash_card_id = card['id'] # This is id of the card in the dashboard (different from id of the card itself)
        self.delete('/api/dashboard/{}/cards'.format(dup_dashboard_id), params={'dashcardId':dash_card_id})
        # adding the new card to the duplicated dashboard
        self.post('/api/dashboard/{}/cards'.format(dup_dashboard_id), json=card_json)
      
    return dup_dashboard_id
  
  

  def copy_collection(self, source_collection_name=None, source_collection_id=None, 
                      destination_collection_name=None,
                      destination_parent_collection_name=None, destination_parent_collection_id=None, 
                      deepcopy_dashboards=False, postfix='', child_items_postfix='', verbose=False):
    """
    Copy the collection with the given name/id into the given destination parent collection. 
    
    Keyword arguments:
    source_collection_name -- name of the collection to copy (default None) 
    source_collection_id -- id of the collection to copy (default None) 
    destination_collection_name -- the name to be used for the collection in the destination (default None).
                                   If None, it will use the name of the source collection + postfix.
    destination_parent_collection_name -- name of the destination parent collection (default None). This is the collection that would have the copied collection as a child.
    destination_parent_collection_id -- id of the destination parent collection (default None). This is the collection that would have the copied collection as a child.
    deepcopy_dashboards -- whether to duplicate the cards inside the dashboards (default False). If True, puts the duplicated cards in a collection called 
                           "[dashboard_name]'s duplicated cards" in the same path as the duplicated dashboard.
    postfix -- if destination_collection_name is None, adds this string to the end of source_collection_name to make destination_collection_name.
    child_items_postfix -- this string is added to the end of the child items' names, when saving them in the destination (default '').
    verbose -- prints extra information (default False) 
    """
    ### Making sure we have the data that we need 
    if not source_collection_id:
      if not source_collection_name:
        raise ValueError('Either the name or id of the source collection must be provided.')
      else:
        source_collection_id = self.get_collection_id(source_collection_name)
    
    if not destination_parent_collection_id:
      if not destination_parent_collection_name:
        raise ValueError('Either the name or id of the destination parent collection must be provided.')
      else:
        destination_parent_collection_id = (
          self.get_collection_id(destination_parent_collection_name)
          if destination_parent_collection_name != 'Root'
          else None
        )
    
    if not destination_collection_name:
      if not source_collection_name:
        source_collection_name = self.get_item_name(item_type='collection', item_id=source_collection_id)
      destination_collection_name = source_collection_name + postfix
      
    ### Creating a collection in the destination to hold the contents of the source collection
    res = self.create_collection(destination_collection_name, 
                                 parent_collection_id=destination_parent_collection_id, 
                                 parent_collection_name=destination_parent_collection_name,
                                 return_results=True
                                )
    destination_collection_id = res['id']  

    ### Getting the items to copy
    items = self.get('/api/collection/{}/items'.format(source_collection_id))
    if type(items) == dict:  # in Metabase version *.40.0 the format of the returned result for this endpoint changed
      items = items['data']

    ### copying the items of the source collection to the new collection
    for item in items:
      
      ## copying a collection
      if item['model'] == 'collection':
        collection_id = item['id']
        collection_name = item['name'] 
        destination_collection_name = collection_name + child_items_postfix
        self.verbose_print(verbose, 'Copying the collection "{}" ...'.format(collection_name))
        self.copy_collection(source_collection_id=collection_id,
                             destination_parent_collection_id=destination_collection_id,
                             child_items_postfix=child_items_postfix,
                             deepcopy_dashboards=deepcopy_dashboards,
                             verbose=verbose)
      
      ## copying a dashboard
      if item['model'] == 'dashboard':
        dashboard_id = item['id']
        dashboard_name = item['name']
        destination_dashboard_name = dashboard_name + child_items_postfix
        self.verbose_print(verbose, 'Copying the dashboard "{}" ...'.format(dashboard_name))
        self.copy_dashboard(source_dashboard_id=dashboard_id,
                            destination_collection_id=destination_collection_id,
                            destination_dashboard_name=destination_dashboard_name,
                            deepcopy=deepcopy_dashboards)
      
      ## copying a card
      if item['model'] == 'card':
        card_id = item['id']
        card_name = item['name']
        destination_card_name = card_name + child_items_postfix
        self.verbose_print(verbose, 'Copying the card "{}" ...'.format(card_name))
        self.copy_card(source_card_id=card_id,
                       destination_collection_id=destination_collection_id,
                       destination_card_name=destination_card_name)
        
      ## copying a pulse
      if item['model'] == 'pulse':
        pulse_id = item['id']
        pulse_name = item['name']
        destination_pulse_name = pulse_name + child_items_postfix
        self.verbose_print(verbose, 'Copying the pulse "{}" ...'.format(pulse_name))
        self.copy_pulse(source_pulse_id=pulse_id,
                        destination_collection_id=destination_collection_id,
                        destination_pulse_name=destination_pulse_name)
  
  

  def search(self, q, item_type=None, archived=False):
    """
    Search for Metabase objects (except DBs) and return their basic info. 
    We can limit the search to a certain item type by providing a value for item_type keyword. 

    Keyword arguments:
    q -- search input
    item_type -- to limit the search to certain item types (default:None, means no limit)
    archived -- whether to include archived items in the search
    """
    assert item_type in [None, 'card', 'dashboard', 'collection', 'table', 'pulse', 'segment', 'metric' ]
    assert archived in [True, False]

    res = self.get(endpoint='/api/search/', params={'q':q, 'archived':archived})
    if type(res) == dict:  # bin Metabase version *.40.0 the format of the returned result for this endpoint changed
      res = res['data']
    if item_type is not None:
      res = [ item for item in res if item['model'] == item_type ]

    return res



  def get_card_data(self, card_name=None, card_id=None, collection_name=None, collection_id=None, data_format='json', parameters=None):
    '''
    Run the query associated with a card and get the results.
    The data_format keyword specifies the format of the returned data:
      - 'json': every row is a dictionary of <column-header, cell> key-value pairs  
      - 'csv': the entire result is returned as a string, where rows are separated by newlines and cells with commas.
    To pass the filter values use 'parameters' param:
      The format is like [{"type":"category","value":["val1","val2"],"target":["dimension",["template-tag","filter_variable_name"]]}]
      See the network tab when exporting the results using the web interface, to get the proper format pattern.
    '''
    assert data_format in [ 'json', 'csv' ]
    
    if card_id is None:
      if card_name is None:
        raise ValueError('Either card_id or card_name must be provided.')
      card_id = self.get_item_id(item_name=card_name,
                                 collection_name=collection_name,
                                 collection_id=collection_id,
                                 item_type='card')

    # adding the filter values (if any)
    import json
    params_json = {'parameters':json.dumps(parameters)}

    # getting the results
    res = self.post("/api/card/{}/query/{}".format(card_id, data_format), 'raw', data=params_json)

    # returning the results in the requested format
    if data_format == 'json':
      return json.loads(res.text)
    if data_format == 'csv':
      return res.text.replace('null', '')



  def clone_card(self, card_id, source_table_id, target_table_id, new_card_name=None, new_card_collection_id=None, ignore_these_filters=None):
    """ 
    *** work in progress ***
    Create a new card where the source of the old card is changed from 'source_table_id' to 'target_table_id'. 
    The filters that were based on the old table would become based on the new table.
    In the current version of the function there are some limitations which would be removed in future versions:
      - The column names used in filters need to be the same in the source and target table (except the ones that are ignored by 'ignore_these_filters' param).
      - The source and target tables need to be in the same DB. 

    Keyword arguments:
    card_id -- id of the card
    source_table_id -- The table that the filters of the card are based on
    target_table_id -- The table that the filters of the cloned card would be based on
    new_card_name -- Name of the cloned card. If not provided, the name of the source card is used.
    new_card_collection_id -- The collection that the cloned card should be saved in
    ignore_these_filters -- A list of variable names of filters. The source of these filters would not change in the cloning process.
    """
    card_info = self.get('/api/card/{}'.format(card_id))
    target_table_col_name_id_mapping = self.get_columns_name_id(table_id=target_table_id)
    source_table_col_id_name_mapping = self.get_columns_name_id(table_id=source_table_id, column_id_name=True)
    filters_data = card_info['dataset_query']['native']['template-tags']

    for filter_variable_name, data in filters_data.items():
      if type(ignore_these_filters) == list and filter_variable_name in ignore_these_filters:
        continue
      column_id = data['dimension'][1]
      column_name = source_table_col_id_name_mapping[column_id]
      target_col_id = target_table_col_name_id_mapping[column_name]
      card_info['dataset_query']['native']['template-tags'][filter_variable_name]['dimension'] = ['field', target_col_id, None]

    new_card_json = {}
    for key in ['dataset_query', 'display', 'visualization_settings']:
      new_card_json[key] = card_info[key]

    if new_card_name:
      new_card_json['name'] = new_card_name
    else:
      new_card_json['name'] = card_info['name']

    if new_card_collection_id:
      new_card_json['collection_id'] = new_card_collection_id
    else:
      new_card_json['collection_id'] = card_info['collection_id']

    self.create_card(custom_json=new_card_json, verbose=True)



  def move_to_archive(self, item_type, item_name=None, item_id=None, 
                      collection_name=None, collection_id=None, table_id=None, verbose=False):
    '''Archive the given item. For deleting the item use the 'delete_item' function.'''
    assert item_type in ['card', 'dashboard', 'collection', 'pulse', 'segment']
    
    if not item_id:
      if not item_name:
        raise ValueError('Either the name or id of the {} must be provided.'.format(item_type))
      if item_type == 'collection':
        item_id = self.get_collection_id(item_name)
      elif item_type == 'segment':
        item_id = self.get_segment_id(item_name, table_id)
      else:
        item_id = self.get_item_id(item_type, item_name, collection_id, collection_name)
    
    if item_type == 'segment':
      # 'revision_message' is mandatory for archiving segments
      res = self.put('/api/{}/{}'.format(item_type, item_id), json={'archived':True, 'revision_message':'archived!'})
    else:
      res = self.put('/api/{}/{}'.format(item_type, item_id), json={'archived':True})
    
    if res in [200, 202]:  # for segments the success status code returned is 200 for others it is 202
      self.verbose_print(verbose, 'Successfully Archived.')  
    else: 
      print('Archiving Failed.')
    
    return res

      

  def delete_item(self, item_type, item_name=None, item_id=None, 
                  collection_name=None, collection_id=None, verbose=False):
    '''
    Delete the given item. Use carefully (this is different from archiving).
    Currently Collections and Segments cannot be deleted using the Metabase API.
    '''
    assert item_type in ['card', 'dashboard', 'pulse']
    if not item_id:
      if not item_name:
        raise ValueError('Either the name or id of the {} must be provided.'.format(item_type))
      item_id = self.get_item_id(item_type, item_name, collection_id, collection_name)
      
    return self.delete('/api/{}/{}'.format(item_type, item_id))



  def update_column(self, params,
                    column_id=None, column_name=None, 
                    table_id=None, table_name=None, 
                    db_id=None, db_name=None):
    '''
    Update the column in data model by providing values for 'params'.
    E.g. for changing the column type to 'Category' in data model, use: params={'semantic_type':'type/Category'} 
    (For Metabase versions before v.39, use: params={'special_type':'type/Category'}).
    Other parameter values: https://www.metabase.com/docs/latest/api-documentation.html#put-apifieldid
    '''
    assert type(params) == dict

    # making sure we have the data we need
    if not column_id:
      if not column_name:
        raise ValueError('Either the name or id of the column needs to be provided.')
      
      if not table_id:
        if not table_name:
          raise ValueError('When column_id is not given, either the name or id of the table needs to be provided.')
        table_id = self.get_table_id(table_name=table_name, db_id=db_id, db_name=db_name)
      
      columns_name_id_mapping = self.get_columns_name_id(table_name=table_name, table_id=table_id, db_name=db_name, db_id=db_id)
      column_id = columns_name_id_mapping.get(column_name)
      if column_id is None:
        raise ValueError('There is no column named {} in the provided table'.format(column_name))
        
    res_status_code = self.put('/api/field/{}'.format(column_id), json=params)
    if res_status_code != 200:
      print('Column Update Failed.')

    return res_status_code
      
  

  def add_card_to_dashboard(self, card_id, dashboard_id):
    params = {
      'cardId': card_id
    }
    self.post(f'/api/dashboard/{dashboard_id}/cards',json=params)


  @staticmethod
  def make_json(raw_json, prettyprint=False):
    """Turn the string copied from the Inspect->Network window into a Dict."""
    import json
    ret_dict = json.loads(raw_json)
    if prettyprint:
      import pprint
      pprint.pprint(ret_dict)
      
    return ret_dict


  @staticmethod
  def nested_replace(self, structure, original, new):
      """
      Replaces strings within a json using a dictionary.
      As found in https://stackoverflow.com/questions/50631393/python-replace-values-in-unknown-structure-json-file
      """

      if type(structure) == list:
          return [self.nested_replace(self, item, original, new) for item in structure]

      if type(structure) == dict:
          return {key: self.nested_replace(self, value, original, new)
                  for key, value in structure.items()}

      if structure == original:
          return new
      else:
          return structure


  def export_card(self, source_card_name=None, source_card_id=None,
                  source_collection_name=None, source_collection_id=None):

      """
      ***Work in progress***
      Given a card in a collection, the method returns a generalized version of the card's source json.
      """

      # make sure card is identifiable via name or id
      if not source_card_id:
          if not source_card_name:
              raise ValueError('Either the name or id of the source card must be provided.')
          else:
              source_card_id = self.get_item_id(item_type='card',
                                                item_name=source_card_name,
                                                collection_id=source_collection_id,
                                                collection_name=source_collection_name)

      # get card's source json
      source_card = self.get('/api/card/{}'.format(source_card_id))

      # identify the name of the database used to create the card
      _db_id = source_card['dataset_query']['database']

      source_card['dataset_query']['database'] = \
          self.get_db_info(db_id=_db_id)['name']

      if source_card['dataset_query']['type'] == 'query':
          # identify the name of the table used to create the card
          _table_id = source_card['dataset_query']['query']['source-table']
          _get_table_metadata = self.get_table_metadata(table_id=_table_id, db_id=_db_id)
          _get_db_info = self.get_db_info(db_id=_db_id)

          source_card['dataset_query']['query']['source-table']=\
              self.get_item_name(item_type='table', item_id=_table_id)

          source_card['dataset_query']['query']['source-table-schema'] = _get_table_metadata['schema']

          try:
            source_card['dataset_query']['query']['source-table-dataset']=\
              _get_db_info['details']['dataset-id']
          except:
            pass

          # create a dictionary composed of columns names and their respective ids, according to table and db
          column_dict = self.get_columns_name_id(table_id=_table_id, db_id=_db_id)

          # if card's query is filtered, generalize filter-by fields using column_dict
          if 'filter' in source_card['dataset_query']['query']:
              filter_json = source_card['dataset_query']['query']['filter']
              for key in column_dict:
                  search_term_field = column_dict[key]
                  filter_json = self.nested_replace(self, filter_json, search_term_field, key.lower() + '_field_id')
              source_card['dataset_query']['query']['filter'] = filter_json

          # if card uses a breakout fields for graphs, generalize breakout fields
          if 'breakout' in source_card['dataset_query']['query']:
              breakout_json = source_card['dataset_query']['query']['breakout']
              for key in column_dict:
                  search_term_field = column_dict[key]
                  breakout_json = self.nested_replace(self, breakout_json, search_term_field, key.lower() + '_field_id')
              source_card['dataset_query']['query']['breakout'] = breakout_json

      # create a generalized version of the card's source json
      source_card_export = {
          'name': source_card['name'],
          'dataset_query': source_card['dataset_query'],
          'display': source_card['display']
      }

      return source_card_export


  def import_card(self, source_card_export=None,
                  destination_collection_name=None, destination_collection_id=None,
                  verbose=False):

      """
      ***Work in progress***
      Given a card's source json export, the method degeneralizes json data to fit the context of the metabase
      instance where the card is being imported to.
      """

      # make sure the card's source export exists and is valid
      if not source_card_export:
          raise ValueError('A valid custom export json needs to be provided.')

      # create a first draft of the card's degeneralized source json
      source_card_import = {
          'name': source_card_export['name'],
          'dataset_query': source_card_export['dataset_query'],
          'display': source_card_export['display']
      }

      # identify the id of the database used to create the card in the import context
      _db_name = source_card_export['dataset_query']['database']

      source_card_import['dataset_query']['database'] = \
          self.get_db_id(db_name=_db_name)

      # the key "query" is created when the it is a "simple question" card. When SQL is explicit, then type = native
      if source_card_import['dataset_query']['type'] == 'query':

          # identify the id of the table used to create the card in the import context
          _table_name = source_card_export['dataset_query']['query']['source-table']
          _table_schema = source_card_export['dataset_query']['query']['source-table-schema']
          _db_id = source_card_export['dataset_query']['database']

          source_card_import['dataset_query']['query']['source-table'] = \
              self.get_table_id(table_name=_table_name, table_schema=_table_schema, db_id=_db_id)

          # create a dictionary composed of columns names and their respective ids, according to table and db
          _table_id = source_card_import['dataset_query']['query']['source-table']

          column_dict = self.get_columns_name_id(table_id=_table_id, db_id=_db_id)

          # if card's query is filtered, degeneralize filter-by fields using column_dict
          if 'filter' in source_card_import['dataset_query']['query']:
              filter_json = source_card_import['dataset_query']['query']['filter']
              for key in column_dict:
                  search_term_field = key.lower() + '_field_id'
                  filter_json = self.nested_replace(self, filter_json, search_term_field, column_dict[key])
              source_card_import['dataset_query']['query']['filter'] = filter_json

          # if card uses a breakout fields for graphs, generalize breakout fields
          if 'breakout' in source_card_import['dataset_query']['query']:
              breakout_json = source_card_import['dataset_query']['query']['breakout']
              for key in column_dict:
                  search_term_field = key.lower() + '_field_id'
                  breakout_json = self.nested_replace(self, breakout_json, search_term_field, column_dict[key])
              source_card_import['dataset_query']['query']['breakout'] = breakout_json

      # create card based on the final draft of source_card_import, the degeneralized source json
      res = self.create_card(collection_name=destination_collection_name,
                             collection_id=destination_collection_id,
                             custom_json=source_card_import,
                             verbose=verbose,
                             return_card=True)

      return res['id']


  def export_dashboard(self, source_dashboard_id=None, source_dashboard_name=None,
                       source_collection_id=None, source_collection_name=None):

      """
      ***Work in progress***
      Given a dashboard's source json, the method generalizes json data to fit the context of the metabase
      instance where the dashboard is being imported to.
      """

      # make sure a valid dashboard id or name is provided
      if not source_dashboard_id:
          if not source_dashboard_name:
              raise ValueError('Either the name or id of the source dashboard must be provided.')
          else:
              source_dashboard_id = self.get_item_id(item_type='dashboard',
                                                     item_name=source_dashboard_name,
                                                     collection_id=source_collection_id,
                                                     collection_name=source_collection_name)

      # get dashboard's source json
      source_dashboard = self.get('/api/dashboard/{}'.format(source_dashboard_id))

      # get information from cards found in the given dashboard
      ordered_cards_list = []
      for ii in source_dashboard['ordered_cards']:
          # ii = source_dashboard['ordered_cards'][4]
          # "virtual card" implies the card is a simple text card. No further processing needed
          if 'virtual_card' in ii['visualization_settings']:
              pass
          elif 'dataset_query' in ii['card']:
              if ii['card']['dataset_query']['type'] == 'native':
                  pass
              else:
                  _table_id = ii['card']['table_id']
                  _db_id = ii['card']['database_id']
                  table_name = self.get_item_name(item_type='table', item_id=_table_id)
                  db_name = self.get_db_info(db_id=_db_id)['name']

                  # if parameter mappings exist, the card and dashboard are connected via filters.
                  if not ii['parameter_mappings'] == []:
                      # create a dictionary composed of columns names and their respective ids, according to table and db
                      column_dict = self.get_columns_name_id(table_id=_table_id,
                                                             db_id=_db_id)
                      # generalize parameter mappings using column_dict
                      for jj in ii['parameter_mappings']:
                          target_list = jj['target']
                          for key in column_dict:
                              search_term_field = column_dict[key]
                              target_list = self.nested_replace(self, target_list,
                                                                search_term_field,
                                                                key.lower() + '_field_id')
                          jj['target'] = target_list

          # gather needed dashboard json data for export
          card_meta = {}
          for prop in ['sizeX', 'sizeY', 'col', 'row', 'series', 'parameter_mappings', 'visualization_settings']:
              card_meta[prop] = ii[prop]

          # if virtual card (text card), leave as it is. Otherwise, use the export_card() method to create a export
          # version of each card found in dashboard.
          if 'virtual_card' in card_meta['visualization_settings']:
              card_meta['card'] = {}
          elif 'dataset_query' in ii['card']:
              if ii['card']['dataset_query']['type'] == 'native':
                  card_meta['card'] = self.export_card(source_card_name=ii['card']['name'],
                                                       source_collection_id=ii['card']['collection_id'])
              else:
                  card_meta['card'] = self.export_card(source_card_name=ii['card']['name'],
                                                       source_collection_id=ii['card']['collection_id'])
                  card_meta['card']['db_name'] = db_name
                  # include table and db names to facilitate degeneralization
                  card_meta['card']['table_name'] = table_name
                  card_meta['card']['table_schema'] = self.get_table_metadata(table_id=_table_id)['schema']
                  card_meta['card']['db_name'] = db_name
          ordered_cards_list.append(card_meta)

      # gather final version of exportable dashboard
      source_dashboard_export = {
          "name": source_dashboard['name'],
          "description": source_dashboard['description'],
          "parameters": source_dashboard['parameters'],
          "cache_ttl": source_dashboard['cache_ttl'],
          "collection_id": None,
          "collection_position": None,
          "ordered_cards": ordered_cards_list
      }

      return source_dashboard_export


  def import_dashboard(self,
                       source_dashboard_export=None,
                       destination_dashboard_name=None,
                       destination_collection_id=None, destination_collection_name=None,
                       postfix=''):

      """
      ***Work in progress***
      Given a dashboard's source json export, the method degeneralizes json data to fit the context of the metabase
      instance where the dashboard is being imported to.
      """

      # make sure a valid dashboard json export has been provided
      if not source_dashboard_export:
          raise ValueError('A valid dashboard export json needs to be provided.')

      # get imported dashboard's name
      source_dashboard_name = source_dashboard_export['name']
      if not destination_dashboard_name:
          destination_dashboard_name = source_dashboard_name + postfix

      # make sure a valid destination collection name or id has been provided
      if not destination_collection_id:
          if not destination_collection_name:
              raise ValueError('Either the name or id of the destination collection must be provided.')
          else:
              destination_collection_id = self.get_collection_id(destination_collection_name)
      source_dashboard_export['collection_id'] = destination_collection_id

      # create an initial bare dashboard according to the export json information
      res = self.post('/api/dashboard/', json=source_dashboard_export)
      dashboard_id = res['id']

      # create a collection for the purpose of storing the dashboard's cards.
      res = self.post('/api/collection/',
                           json={'name': destination_dashboard_name + "'s cards",
                                 'color': '#509EE3',
                                 'parent_id': destination_collection_id})
      cards_collection_id = res['id']

      # extract card information from export json and create cards using import_card()
      for ii in source_dashboard_export['ordered_cards']:
          # if card is virtual card (text card), then nothing to import
          if 'virtual_card' in ii['visualization_settings']:
              card_json_dump = {"cardId": None}
              res = self.post('/api/dashboard/' + str(dashboard_id) + '/cards', json=card_json_dump)
              ii['card_id'] = None
              ii['id'] = res['id']
          else:
              card_id = self.import_card(source_card_export=ii['card'],
                                         destination_collection_id=cards_collection_id)
              ii['card']['id'] = card_id
              card_json_dump = {"cardId": card_id}
              res = self.post('/api/dashboard/' + str(dashboard_id) + '/cards', json=card_json_dump)
              ii['card_id'] = card_id
              ii['id'] = res['id']

      # get imported cards' order and size
      ordered_cards_import = []
      for ii in source_dashboard_export['ordered_cards']:
          if 'virtual_card' in ii['visualization_settings']:
              pass
          else:
              if not ii['parameter_mappings'] == []:
                  card_id = ii['card']['id']
                  # create a dictionary composed of columns names and their respective ids, according to table and db
                  _table_id = self.get_table_id(table_name=ii['card']['table_name'],
                                                table_schema=ii['card']['table_schema'],
                                                db_name=ii['card']['db_name'])

                  column_dict = self.get_columns_name_id(table_id=_table_id)

                  # degeneralize parameter mappings using column_dict
                  for jj in ii['parameter_mappings']:
                      jj['card_id'] = card_id
                      target_list = jj['target']
                      for key in column_dict:
                          search_term_field = key.lower() + '_field_id'
                          target_list = self.nested_replace(self, target_list, search_term_field, column_dict[key])
                      jj['target'] = target_list

          # get needed order and size information for each card, and gather in one list
          card_order_info = {}
          for prop in ['id', 'card_id', 'visualization_settings', 'col', 'row', 'sizeX', 'sizeY', 'series',
                       'parameter_mappings']:
              card_order_info[prop] = ii[prop]
          ordered_cards_import.append(card_order_info)

      # update dashboard with cards' order and size information
      card_json_order = {"cards": ordered_cards_import}
      res = self.put('/api/dashboard/' + str(dashboard_id) + '/cards', json=card_json_order)

      if res == 200:
          return (print('Your dashboard has been imported'))
