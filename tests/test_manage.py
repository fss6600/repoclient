import logging
import os
import sys
import unittest
from collections import Counter, namedtuple
from pprint import pprint
import copy
from eiisclient.core.manage import Action, Status, Manager
from eiisclient.core.utils import get_temp_dir, gzip_read, from_json, to_json, file_hash_calc
from eiisclient.core.exceptions import *
from tests.utils import create_test_repo
from tests.eiisrepo.eiisrepo import Manager as Repomanager
from collections.abc import Iterator


class ManageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = get_temp_dir(prefix='workdir_')
        cls.repodir = get_temp_dir(prefix='repodir_')
        cls.eiispath = get_temp_dir(prefix='eiis_')

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()
        cls.repodir.cleanup()
        cls.eiispath.cleanup()

    def test_action_class(self):
        update = Action.update
        install = Action.install
        delete = Action.delete
        self.assertEqual(install.value, 0)
        self.assertEqual(update.value, 1)
        self.assertEqual(delete.value, 2)

    def setUp(self):
        logger = logging.getLogger(__name__)
        logger.addHandler(logging.StreamHandler(sys.stdout))
        self.manager = Manager(self.repodir.name, workdir=self.workdir.name, eiispath=self.eiispath.name,
                               logger=logger)

    def test_manager_functions(self):
        # self.manager = Manager(self.repodir.name, workdir=self.workdir.name, eiispath=self.eiispath.name)

        # статус диспетчера
        self.assertFalse(self.manager.activated)


        # определение действий над пакетами
        installed = ['P1', 'P2', 'P3']
        selected = ['P1', 'P4']
        i, u, d = self.manager.get_lists_difference(installed, selected)
        install = ['P4']
        update = ['P1']
        delete = ['P2', 'P3']
        self.assertListEqual(install, list(i))
        self.assertListEqual(update, list(u))
        self.assertListEqual(delete, list(d))

        # локального индекса еще нет
        self.assertDictEqual(self.manager.get_local_index(), {})

        # диспетчер еще не активирован
        with self.assertRaises(DispatcherNotActivated):
            self.manager.get_remote_index()

        # пакеты еще не установлены
        self.assertFalse(self.manager.local_packet_exists('Ревизор'))
        self.assertEqual(self.manager.get_installed_packets_list(), ())
        self.assertEqual(self.manager.get_selected_packets_list(), ())

        # буфер еще не создан
        self.assertTrue(self.manager.buffer_is_empty())


class ManageWorkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = get_temp_dir(prefix='workdir_')
        cls.repodir = get_temp_dir(prefix='repodir_')
        cls.eiispath = get_temp_dir(prefix='eiisdir_')

        cls.logger = logging.getLogger(__name__)
        cls.logger.addHandler(logging.StreamHandler(sys.stdout))

        # создаем тестовый репозиторий
        create_test_repo(cls.repodir.name)
        cls.repomanager = Repomanager(cls.repodir.name)
        cls.repomanager.index()

        index_file_path = os.path.join(cls.repodir.name, 'Index.gz')
        index_file_path_hash = os.path.join(cls.repodir.name, 'Index.gz.sha1')
        cls.remote_test_index = from_json(gzip_read(index_file_path))
        with open(index_file_path_hash) as fp:
            cls.remote_test_index_hash = fp.read()

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()
        cls.repodir.cleanup()
        cls.eiispath.cleanup()

    def setUp(self):

        self.manager = Manager(self.repodir.name, workdir=self.workdir.name, eiispath=self.eiispath.name,
                               logger=self.logger)

        self.test_packet_name = 'Бухгалтерия'
        self.packets_list = ([self.test_packet_name])
        self.repomanager.index()
        self.tempdir = get_temp_dir(prefix='tempdir_')

    def tearDown(self):
        self.tempdir.cleanup()

    def test_eiisclient_first_start(self):
        # print(self.repodir.name)
        # print('\n press any key')
        #
        # input()

        self.manager.activate()

        # get remote index
        index = self.manager.get_remote_index()
        self.assertIsNotNone(index)
        self.assertIsInstance(index, dict)

        # проверка обновлений в репозитории
        self.assertTrue(self.manager.repo_updated())

        # проверка статуса локального пакета
        os.makedirs(os.path.join(self.eiispath.name, self.test_packet_name))
        self.assertEqual(self.manager.get_local_packet_status(self.test_packet_name), Status.installed, 'неверный статус')
        self.assertEqual(self.manager.get_local_packet_status('Ревизор'), Status.purged, 'неверный статус')

        test_packet_name = 'ТЕСТ_ПАКЕТ'
        test_packet_name_removed = '{}.removed'.format(test_packet_name)
        os.mkdir(os.path.join(self.eiispath.name, test_packet_name_removed))  # пакет со статусом удаленный

        self.assertEqual(self.manager.get_local_packet_status(test_packet_name), Status.removed, 'неверный статус')
        self.assertFalse(self.manager.local_packet_exists(test_packet_name))

        res = self.manager.claim_packet(test_packet_name)  # восстанавливаем удаленный пакет, если статус удален
        self.assertTrue(res)
        self.assertEqual(self.manager.get_local_packet_status(test_packet_name), Status.installed, 'неверный статус')

        res = self.manager.claim_packet(self.test_packet_name)  # пакет присутствует, все норм
        self.assertTrue(res)
        os.removedirs(os.path.join(self.eiispath.name, self.test_packet_name))

        ###
        # repo is busy
        self.repomanager.fd.init()
        with self.assertRaises(RepoIsBusy):
            self.manager.repo_busy_check()

        self.repomanager.fd.clean()
        self.repomanager.index()

        # статус переменных после деактивации
        self.manager.deactivate()
        self.assertIsNone(self.manager.disp)
        self.assertIsNone(self.manager.local_index)
        self.assertIsNone(self.manager.remote_index)
        self.assertDictEqual(self.manager.action_list, {})

    def test_manager_parse_data_by_action(self):
        self.manager.activate()

        # диспетчер активирован
        self.assertTrue(self.manager.activated)

        self.manager.remote_index = self.manager.get_remote_index()
        self.manager.local_index = self.manager.get_remote_index()

        self.assertIsNot(self.manager.remote_index, {}, 'почему пустой словарь')
        self.assertIn(self.test_packet_name, self.manager.remote_index.keys(), 'отсутствут пакет в индексе')

        # action.install
        res = self.manager.parse_data_by_action(self.packets_list, Action.install)
        self.assertIsInstance(res, Iterator, 'должен быть генератор')

        res = list(res)
        files = self.manager.remote_index[self.test_packet_name].get('files')

        self.assertIsNotNone(files, 'ожидался словарь')
        self.assertIsInstance(files, dict, 'ожидался словарь')
        self.assertEqual(len(res), len(files.keys()), 'неравное количество значений')

        for packname, action, src, crc in res:
            self.assertIsInstance(packname, str, 'ожидалась строка')
            self.assertIsInstance(src, str, 'ожидалась строка')
            self.assertIsInstance(crc, str, 'ожидалась строка')
            self.assertIsInstance(action, Action, 'ожидался экземпляр Action')

            s = files.get(src)
            self.assertIsNotNone(s, 'ожидалась строка')
            self.assertEqual(s, crc, 'неравные значения')

            self.assertEqual(action, Action.install)

        # action.update - do nothing
        res = self.manager.parse_data_by_action(self.packets_list, Action.update)
        self.assertIsInstance(res, Iterator, 'должен быть генератор')

        res = list(res)
        self.assertTrue(len(res) == 0, 'обновлять нечего - список должен быть пустым')


        # action.update - патчим данные индекс-файлов

        new_data = copy.deepcopy(self.manager.local_index[self.test_packet_name])
        new_data['phash'] = '0000'
        new_data['files'].update({'F4_2006_21.dbf': '0000'})
        new_data['files'].update({'compkeep.exe': '0000'})
        self.manager.local_index[self.test_packet_name] = new_data  # данные для обновления
        self.manager.remote_index[self.test_packet_name]['files'].pop('file_must_be_delete')  # для удаления локального файла
        self.manager.remote_index[self.test_packet_name]['files'].update({'new_file': '0000'})  # для установки локального файла

        res = self.manager.parse_data_by_action(self.packets_list, Action.update)
        res = list(res)

        self.assertEqual(len(res), 4, 'должно быть равным 4')
        counter = Counter()

        for packname, action, src, crc in res:
            counter[action] += 1
            if action == Action.install:
                self.assertEqual(src, 'new_file')
                self.assertEqual(crc, '0000')

            elif action == Action.update:
                self.assertIn(src, ['F4_2006_21.dbf', 'compkeep.exe'])
                self.assertNotEqual(crc, '0000')

            elif action == Action.delete:
                self.assertEqual(src, 'file_must_be_delete')
                self.assertIsNone(crc)

        self.assertEqual(counter[Action.install], 1)
        self.assertEqual(counter[Action.delete], 1)
        self.assertEqual(counter[Action.update], 2)

        # action.delete
        res = self.manager.parse_data_by_action(self.packets_list, Action.delete)
        res = list(res)
        self.assertEqual(len(res), 1)
        self.assertListEqual(res, self.packets_list)

    def test_manager_get_task(self):
        self.manager.activate()

        # диспетчер активирован
        self.assertTrue(self.manager.activated)

        self.manager.remote_index = self.manager.get_remote_index()
        self.manager.local_index = self.manager.get_remote_index()
        new_data = copy.deepcopy(self.manager.local_index[self.test_packet_name])
        new_data['phash'] = '0000'
        new_data['files'].update({'compkeep.exe': '0000'})
        self.manager.local_index[self.test_packet_name] = new_data  # данные для обновления
        self.manager.remote_index[self.test_packet_name]['files'].update({'new_file': '0000'})

        self.manager.action_list['install'] = self.manager.parse_data_by_action(self.packets_list, Action.install)
        self.manager.action_list['update'] = self.manager.parse_data_by_action(self.packets_list, Action.update)

        res = list(self.manager.get_task())

        action_count = Counter()
        files = self.manager.remote_index[self.test_packet_name]['files']
        files_src = [os.path.join(self.manager.disp.repopath, self.test_packet_name, file) for file in files]
        files_dst = [os.path.join(self.manager.buffer, self.test_packet_name, file) for file in files]

        for task in res:
            action_count[task.action] += 1
            if task.action == Action.install:
                self.assertIn(task.src, files_src)
                self.assertIn(task.dst, files_dst)
                fp = os.path.relpath(task.dst, os.path.join(self.manager.buffer, self.test_packet_name))
                self.assertEqual(task.crc, self.manager.remote_index[self.test_packet_name]['files'][fp])
            elif task.action == Action.update:
                self.assertIn(os.path.basename(task.src), ('compkeep.exe', 'new_file'))
                self.assertIn(os.path.basename(task.dst), ('compkeep.exe', 'new_file'))
                self.assertIn(len(task.crc), (4, 40))
                self.assertIsInstance(task.src, str)
                self.assertIsInstance(task.dst, str)
                self.assertIsInstance(task.crc, str)
            # else:
            #     self.assertFalse(True, 'неопределенное действие')

    def test_get_installed_packets_list(self):
        ##  no eiispath
        dirname = os.path.join('C:\\', 'test_78540297589')
        self.manager.eiispath = dirname
        res = self.manager.get_installed_packets_list()

        self.assertEqual(self.manager.eiispath, dirname)
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 0)

        ##
        eiispath = self.tempdir.name
        self.manager.eiispath = eiispath
        self.manager.activate()

        self.assertEqual(self.manager.eiispath, eiispath)

        # no eiis
        res = self.manager.get_installed_packets_list()
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 0)

        #
        installed = ('Бухгалтерия', 'Ревизор', 'Форма 4')
        removed = ('ОКВЭД', 'Льготные путевки', 'Санкур')

        for name in installed:
            os.makedirs(os.path.join(eiispath, name))

        for name in removed:
            os.makedirs('{}.removed'.format(os.path.join(eiispath, name)))


        ##  3 eiis
        res = self.manager.get_installed_packets_list()
        # print(res)
        # print(os.listdir(eiispath))
        # print(os.listdir(self.manager.eiispath))
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 3)
        # self.assertIn('Форма 4', res)
        self.assertListEqual(list(res), list(installed))

    def test_get_selected_packets_list(self):
        self.manager.selected_packets_list_file = os.path.join(self.tempdir.name, 'selected')
        res = self.manager.get_selected_packets_list()

        # no file
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 0)

        # from file
        with open(self.manager.selected_packets_list_file, 'w') as fp:
            fp.write('# comment\n')
            fp.write('\n')
            fp.write('Бухгалтерия\n')
            fp.write('Ревизор\n')
            fp.write('# Форма 4\n')

        res = self.manager.get_selected_packets_list()
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 2)
        self.assertIn('Бухгалтерия', res)

    def test_delete_packets(self):
        packs = ('Форма 6', 'Анкета страхователя', 'Делопроизводство', 'Ревизор', 'Регистратор',
                 'Реестр листков нетрудоспособности','Форма 4', 'Справочник ОКВЭД-ОКОНХ','Страховые случаи',
                 'Профилактика')
        packs_for_delete_1 = ['Форма 6', 'Анкета страхователя', 'Делопроизводство']
        packs_for_delete_2 = ['Профилактика', 'Справочник ОКВЭД-ОКОНХ', 'Ревизор']

        # make eiis packets
        for name in packs:
            os.makedirs(os.path.join(self.eiispath.name, name))

        self.manager.action_list['delete'] = iter(packs_for_delete_1)
        self.manager.activate()

        self.manager.delete_packets()
        res = os.listdir(self.eiispath.name)
        self.assertEqual(len(res), len(packs))  # пакеты не удалены
        for name in packs_for_delete_1:
            self.assertIn('{}.removed'.format(name), res)

        self.manager.action_list['delete'] = iter(packs_for_delete_2)
        self.manager.purge = True
        self.manager.delete_packets()
        res = os.listdir(self.eiispath.name)

        self.assertEqual(len(res), len(packs) - len(packs_for_delete_2))
        for name in packs_for_delete_2:
            self.assertNotIn(name, res)

    def test_get_index(self):
        ## remote index
        with self.assertRaises(DispatcherNotActivated):
            self.manager.get_remote_index()

        self.manager.activate()

        res = self.manager.get_remote_index()

        self.assertIsInstance(res, dict)
        self.assertIn('Бухгалтерия', res.keys())

        ## local index
        res1 = self.manager.get_local_index()
        self.assertIsInstance(res1, dict)
        self.assertDictEqual(res1, {})

        with open(self.manager.local_index_file, 'w') as fp:
            fp.write(to_json(res))

        res2 = self.manager.get_local_index()
        self.assertIsInstance(res2, dict)
        self.assertIn('Бухгалтерия', res2.keys())

    def test_install_packets(self):
        installed = {
            'Бухгалтерия':
                [('compkeep.exe', 2048),
                 ('compkeep.ini', 3072),
                 ('F4_2006_21.dbf', 57344),
                 ('template\\0504089.xls', 71680),
                 ('template\\AccRotor.frf', 4096)],
            'RapRep':
                [('RapRep.exe', 1328128),
                 ('history.txt', 1024),
                 ('RapRepu.chm', 44032)],
            }

        updated = {
            'Бухгалтерия':
                [('compkeep.exe', 21548),
                 ('compkeep.ini', 3087),
                 ('F4_2006_21.dbf', 57344),
                 ('F4_2006_22.dbf', 57344),
                 ('template\\0504089.xls', 71680),
                 ('template\\0504090.xls', 54897),
                 ('template\\AccRotor.frf', 4096)],
            'Custom':
                [('custom.exe', 1024),
                 ('readme.txt', 24568),
                 ('tmp\\data.log', 1234)]
            }

        fn = os.path.join(self.manager.eiispath, 'Бухгалтерия', 'compkeep.exe')
        create_test_repo(self.manager.eiispath, create_random=False, packages=installed)
        create_test_repo(self.manager.buffer, create_random=False, packages=updated)
        somefile = os.path.join(self.manager.buffer, 'some_file.dat')

        with open(somefile, 'w') as fp:
            fp.write('test')

        self.assertEqual(os.path.getsize(fn), 2048)
        self.assertIn(os.path.basename(somefile), os.listdir(self.manager.buffer))
        self.assertNotEqual(len(os.listdir(self.manager.buffer)), 0)
        self.assertEqual(len(os.listdir(self.manager.buffer)), 4)
        # self.assertEqual(len(os.listdir(self.manager.eiispath)), 2)
        self.assertFalse(self.manager.buffer_is_empty())

        # with open(fn), self.assertLogs(self.logger, level='ERROR') as cm:
        #         self.manager.install_packets()
        #         self.assertLogs(cm.output, 'ошибка установки пакета Бухгалтерия')

        with open(fn, 'rb'): #, self.assertRaises(PacketInstallError):
            self.manager.install_packets()

        self.assertEqual(os.path.getsize(fn), 21548)

        self.manager._clean_buffer()
        self.assertTrue(self.manager.buffer_is_empty())

    def test_handle_files(self):
        # подготовка файлов в репозитории
        self.manager = Manager(self.repodir.name, workdir=self.workdir.name, eiispath=self.eiispath.name,
                               logger=self.logger, threads=3)

        new_packet = {
            'Новый пакет': [('Новый небитый файл', 2048),
                            ('Новый небитый файл2', 2048),
                            ('Новый небитый файл3', 2048),
                            ('Новый небитый файл4', 2048),
                            ('Новый небитый файл5', 2048),
                            ('Новый небитый файл6', 2048),
                            ('Новый битый файл', 4096)]
            }

        create_test_repo(self.manager.repo, create_random=False, packages=new_packet)

        fp = os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл')
        fp_hash = file_hash_calc(fp)

        self.manager.activate()
        self.manager.action_list['install'] = [
            ('Новый пакет', Action.install, 'Новый небитый файл', fp_hash),
            ('Новый пакет', Action.install, 'Новый небитый файл2', file_hash_calc(
                os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл2'))),
            ('Новый пакет', Action.install, 'Новый небитый файл3', file_hash_calc(
                os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл3'))),
            ('Новый пакет', Action.install, 'Новый небитый файл4', file_hash_calc(
                os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл4'))),
            ('Новый пакет', Action.install, 'Новый небитый файл5', file_hash_calc(
                os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл5'))),
            ]

        self.manager.action_list['update'] = []

        self.assertTrue(self.manager.buffer_is_empty())

        self.manager.handle_files()

        fpath = os.path.join(self.manager.buffer, 'Новый пакет', 'Новый небитый файл')
        self.assertFalse(self.manager.buffer_is_empty())
        self.assertIn('Новый пакет', os.listdir(self.manager.buffer))
        self.assertTrue(os.path.exists(fpath))
        self.assertEqual(fp_hash, file_hash_calc(fpath))
        self.assertEqual(len(os.listdir(self.manager.buffer)), 1)
        self.assertEqual(len(os.listdir(os.path.join(self.manager.buffer, 'Новый пакет'))), 5)

        ## handle corrupted file
        self.manager.action_list['install'] = [
            ('Новый пакет', Action.install, 'Новый битый файл', fp_hash[:-1]),
            ('Новый пакет', Action.install, 'Новый небитый файл6', file_hash_calc(
                os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл6'))),
            ]

        with self.assertRaises(DownloadPacketError):
            self.manager.handle_files()

        self.assertTrue(os.path.exists(os.path.join(self.manager.buffer,'Новый пакет', 'Новый небитый файл6')))
        self.assertFalse(os.path.exists(os.path.join(self.manager.buffer,'Новый пакет', 'Новый битый файл')))

        self.manager.install_packets()
        self.assertTrue(os.path.exists(os.path.join(self.manager.eiispath, 'Новый пакет', 'Новый небитый файл')))
        self.assertTrue(os.path.exists(os.path.join(self.manager.eiispath, 'Новый пакет', 'Новый небитый файл5')))

        ## handle update/delete files
        old_crc = file_hash_calc(os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл6'))
        new_packet = {
            'Новый пакет': [('Новый небитый файл6', 2048 * 10)]
            }

        create_test_repo(self.manager.repo, create_random=False, packages=new_packet)

        new_crc = file_hash_calc(os.path.join(self.manager.repo, 'Новый пакет', 'Новый небитый файл6'))
        self.manager.action_list['install'] = []
        self.manager.action_list['update'] = [
            ('Новый пакет', Action.delete, 'Новый небитый файл', None),
            ('Новый пакет', Action.delete, 'Неизвестный файл', None),
            ('Новый пакет', Action.update, 'Новый небитый файл6', new_crc),

            ]

        self.manager.handle_files()

        self.assertFalse(os.path.exists(os.path.join(self.manager.eiispath, 'Новый пакет', 'Новый небитый файл')))
        self.assertNotEqual(old_crc, new_crc)
        self.assertEqual(os.path.getsize(os.path.join(self.manager.buffer, 'Новый пакет', 'Новый небитый файл6')),
                         2048 * 10)


class ManageWholeProcessCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = get_temp_dir(prefix='workdir_')
        cls.repodir = get_temp_dir(prefix='repodir_')
        cls.eiispath = get_temp_dir(prefix='eiisdir_')

        cls.logger = logging.getLogger(__name__)
        cls.logger.addHandler(logging.StreamHandler(sys.stdout))

        # создаем тестовый репозиторий
        create_test_repo(cls.repodir.name)
        cls.repomanager = Repomanager(cls.repodir.name)
        cls.repomanager.index()

        index_file_path = os.path.join(cls.repodir.name, 'Index.gz')
        index_file_path_hash = os.path.join(cls.repodir.name, 'Index.gz.sha1')
        cls.remote_test_index = from_json(gzip_read(index_file_path))
        with open(index_file_path_hash) as fp:
            cls.remote_test_index_hash = fp.read()

    @classmethod
    def tearDownClass(cls):
        print('\n press any key')
        input()

        cls.workdir.cleanup()
        cls.repodir.cleanup()
        cls.eiispath.cleanup()

    def setUp(self):
        self.repomanager.index()

        self.manager = Manager(self.repodir.name, workdir=self.workdir.name, eiispath=self.eiispath.name,
                               logger=self.logger)
        self.installed = self.manager.get_installed_packets_list()
        self.selected = self.manager.get_selected_packets_list()

    def tearDown(self):
        pass

    def test_start_from_zero(self):
        self.manager.start(self.installed, self.selected)

        self.assertTrue(self.manager.buffer_is_empty())
        self.assertSequenceEqual(self.manager.get_installed_packets_list(), ())
        self.assertSequenceEqual(self.manager.get_local_index(), ())
        self.assertIsNone(self.manager.get_local_index_hash())

        ## подготовка к следующему тесту: установка подсистемы Бухгалтерия
        with open(self.manager.selected_packets_list_file, 'w') as fp:
            fp.write('Бухгалтерия')

    def test_start_install_packet(self):
        self.manager.start(self.installed, self.selected)

        # self.assertTrue(self.manager.buffer_is_empty())
        self.assertSequenceEqual(self.manager.get_installed_packets_list(), ('Бухгалтерия',))
        # self.assertDictEqual(self.manager.get_local_index(), {})
        # self.assertIsNone(self.manager.get_local_index_hash())

if __name__ == '__main__':  # pragma: nocover
    unittest.main()
