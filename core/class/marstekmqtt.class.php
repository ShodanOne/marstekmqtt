<?php
/* This file is part of Jeedom.
*
* Jeedom is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Jeedom is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with Jeedom. If not, see <http://www.gnu.org/licenses/>.
*/

/* * ***************************Includes********************************* */
require_once __DIR__  . '/../../../../core/php/core.inc.php';



class marstekmqtt extends eqLogic {
  
  const PYTHON_PATH = __DIR__ . '/../../resources/venv/bin/python3';
  /*     * *************************Attributs****************************** */
  
  /* ----- Daemon ----- */
  
  public static function isrunning()
  {
    $test = true;
    $pid_file = jeedom::getTmpFolder(__CLASS__) . '/deamon.pid';
    if (file_exists($pid_file))
    {
      if (@posix_getsid(trim(file_get_contents($pid_file))))
      {
        $test = true;
      }
      else
      {
        shell_exec(system::getCmdSudo() . 'rm -rf ' . $pid_file . ' 2>&1 > /dev/null');
        return false;
      }
    }
    else
    {
      if (config::byKey('RemoteDemon',__CLASS__) == false)
      {
      	return false;
      }
    }
    
    
    $result = mqtt2::getPluginForTopic(config::byKey('topic', __CLASS__, 'marstek'));
    //log::add(__CLASS__, 'debug', "isrunning result = " . $result);
    if ($result == __CLASS__)
      $test=true;
    else
      $test=false;
    return $test;
  }
  
  public static function deamon_info()
  {
    
    //log::add(__CLASS__, 'debug', "Execution daemon_info");
    $return = array();
    $return['log'] = __CLASS__;
    $return['state'] = 'nok';
    $return['launchable'] = 'ok';
    
    $port = intval(config::byKey('apiPort', __CLASS__, 30000));
    if ($port == 0) {
      log::add(__CLASS__, 'debug', "Invalid API port : ". strval($port));
      $return['launchable'] = 'nok';
    }
    
    $timeout = intval(config::byKey('apiTimeout', __CLASS__, 5));
    if ($timeout == 0) {
      log::add(__CLASS__, 'debug', "Invalid timeout value : ". strval($timeout). " (must be >0)");
      $return['launchable'] = 'nok';
    }
    
    $retry = intval(config::byKey('apiRetry', __CLASS__, 3));
    if ($retry == 0) {
      log::add(__CLASS__, 'debug', "Invalid retry value : ". strval($retry). " (must be >0)");
      $return['launchable'] = 'nok';
    }
    
    $period = intval(config::byKey('period', __CLASS__, 10));
    if ($period == 0) {
      log::add(__CLASS__, 'debug', "Invalid period value : ". strval($period). " (must be >0)");
      $return['launchable'] = 'nok';
    }
    
    if (!class_exists('mqtt2')) {
      $return['launchable'] = 'nok';
      $return['launchable_message'] = __("Le plugin MQTT Manager n'est pas installé", __FILE__);
    } else {
      if (mqtt2::deamon_info()['state'] != 'ok') {
        $return['launchable'] = 'nok';
        $return['launchable_message'] = __("Le démon MQTT Manager n'est pas démarré", __FILE__);
      }
    }
    
    if (self::isrunning()) {
      $return['state'] = 'ok';
    } else {
      $return['state'] = 'nok';
    }
    return $return;
  }
  
  public static function deamon_start()
  {
    log::add(__CLASS__, 'debug', "Execution daemon_start");
    self::deamon_stop();
    $deamon_info = self::deamon_info();
    if ($deamon_info['launchable'] != 'ok') {
      throw new Exception(__('Veuillez vérifier la configuration', __FILE__));
    }
    
    // Recupération des parametres
    $port = intval(config::byKey('apiPort', __CLASS__, 30000));
    $timeout = intval(config::byKey('apiTimeout', __CLASS__, 5));
    $retry = intval(config::byKey('apiRetry', __CLASS__, 3));
    $period = intval(config::byKey('period', __CLASS__, 10));
    $localdemon = !intval(config::byKey('RemoteDemon', __CLASS__));
    
    // Recuperatino des parametres mqtt2
    $mqtt = mqtt2::getFormatedInfos();
    $mqttip = $mqtt['ip'];
    $mqttport = (isset($mqtt['port'])) ? intval($mqtt['port']) : 1883;
    $mqttuser = $mqtt['user'];
    $mqttpassword = $mqtt['password'];
    
    // Recuperation du niveau de log
    $loglev = log::convertLogLevel(log::getLogLevel(__CLASS__));
    //$loglev = 'info';
    
    // Recuperation du chemin
    $path = realpath(dirname(__FILE__) . '/../../resources/marstekmqttd');
    log::add(__CLASS__, 'debug', "chemin = ". $path);
                     
    // Construction de la commande avec ses parametres
    $cmd = system::getCmdPython3(__CLASS__) . " {$path}/marstekmqttd.py";
    $cmd = self::PYTHON_PATH . " {$path}/marstekmqttd.py";
    #$cmd .= ' --port='.$port;
    $cmd .= ' --mqtt_address="'.$mqttip.'"';
    #$cmd .= ' --mqtt_client="'.$topic.'"';
    $cmd .= ' --mqtt_port='.$mqttport;
    $cmd .= ' --mqtt-username="'.$mqttuser.'"';
    $cmd .= ' --mqtt-password="'.$mqttpassword.'"';
    $cmd .= ' --timeout='.$timeout;
    $cmd .= ' --retry='.$retry;
    $cmd .= ' --poll_period='.$period;
    $cmd .= ' --log='.$loglev;
    $cmd .= ' --pidfile='.jeedom::getTmpFolder(__CLASS__) . '/deamon.pid';
    log::add(__CLASS__, 'debug', "commande = ". $cmd);
    
    // Declaration au plugin mqtt
    mqtt2::addPluginTopic(__CLASS__, 'marstek');
    //mqtt2::addPluginTopic(__CLASS__, 'airzone');
    
    // Lancement du demon
    if ($localdemon) {
      log::add(__CLASS__, 'debug', 'Lancement demon en local => '.$cmd);
      $result = exec($cmd . ' >> ' . log::getPathToLog('marstekmqtt_daemon') . ' 2>&1 &');
      $i = 0;
      while ($i < 20) {
        $deamon_info = self::deamon_info();
        if ($deamon_info['state'] == 'ok') {
          break;
        }
        sleep(1);
        $i++;
      }
      if ($i >= 30) {
        log::add(__CLASS__, 'error', __('Impossible de lancer le démon, vérifiez le log', __FILE__), 'unableStartDeamon');
        return false;
      }
    }
    
    message::removeAll(__CLASS__, 'unableStartDeamon');
   	return true;
  }
  
  public static function deamon_stop()
  {
    log::add(__CLASS__, 'debug', "Execution daemon_stop");
    
    $localdemon = !intval(config::byKey('RemoteDemon', __CLASS__));
    if ($localdemon) {
    	$pid_file = jeedom::getTmpFolder(__CLASS__) . '/deamon.pid'; // ne pas modifier
    	if (file_exists($pid_file)) {
    		$pid = intval(trim(file_get_contents($pid_file)));
        	system::kill($pid);
    	}
    	system::kill('marstekmqttd.py'); // nom du démon à modifier
    	sleep(1);
    }
    mqtt2::removePluginTopicByPlugin(__CLASS__);
  }
  
  /* ----- Methodes statiques ----- */
  
  /* ---- Methodes statiques pour dependances et enviroonement ---- */
  public static function backupExclude()
  {
	return ['resources/venv'];
  }
  
  public static function dependancy_install()
  {
    //log::add(__CLASS__, 'debug', "Execution dependancy_install");
    log::remove(__CLASS__ . '_update');
    return array('script' => dirname(__FILE__) . '/../../resources/install_apt.sh ' . jeedom::getTmpFolder(__CLASS__) . '/dependance', 'log' => log::getPathToLog(__CLASS__ . '_update'));
  }
  
  public static function dependancy_info()
  {
    //log::add(__CLASS__, 'debug', "Execution dependancy_info");
    $return = array();
    $return['log'] = log::getPathToLog(__CLASS__ . '_update');
    $return['progress_file'] = jeedom::getTmpFolder(__CLASS__) . '/dependance';
    $return['state'] = 'ok';
    if (file_exists(jeedom::getTmpFolder(__CLASS__) . '/dependance'))
    {
      $return['state'] = 'in_progress';
    } 
    elseif (!file_exists(self::PYTHON_PATH))
    {
      $return['state'] = 'nok';
    }
    elseif (!self::pythonRequirementsInstalled(self::PYTHON_PATH, __DIR__ . '/../../resources/requirements.txt'))
    {
      $return['state'] = 'nok';
    }
    return $return;
  }
  
  private static function pythonRequirementsInstalled(string $pythonPath, string $requirementsPath)
  {
    if (!file_exists($pythonPath) || !file_exists($requirementsPath))
    {
      return false;
	}
	exec("{$pythonPath} -m pip freeze", $packages_installed);
	$packages = join("||", $packages_installed);
	exec("cat {$requirementsPath}", $packages_needed);
	foreach ($packages_needed as $line)
    {
      if (preg_match('/([^\s]+)[\s]*([>=~]=)[\s]*([\d+\.?]+)$/', $line, $need) === 1)
      {
        if (preg_match('/' . $need[1] . '==([\d+\.?]+)/i', $packages, $install) === 1)
        {
          if ($need[2] == '==' && $need[3] != $install[1])
          {
            return false;
		  }
          elseif (version_compare($need[3], $install[1], '>'))
          {
            return false;
		  }
		}
        else
        {
		  return false;
		}
	  }
	}
	return true;
  }
  
  /* ---- Methodes statiques perso ---- */
  public static function createDevice($src, $name)
  {
    //log::add(__CLASS__, 'debug', 'createDevice : src='.$src.' - name='.$name);
    $eqt = new marstekmqtt();
    $eqt->setName($src);
    $eqt->setEqType_name(__CLASS__);
    $eqt->setConfiguration('src', $src);
    $eqt->setConfiguration('name', $name);
    $eqt->setConfiguration('id', 999);
    $eqt->setConfiguration('ip', 'x');
    $eqt->setConfiguration('ble_mac', 'x');
    $eqt->setConfiguration('wifi_mac', 'x');
    $eqt->setConfiguration('firmware', 999);
    $eqt->setConfiguration('wifi_name', 'x');
    $eqt->setConfiguration('wifi_name', 'x');
    $eqt->setConfiguration('rated_capacity', 'x');
    $eqt->setConfiguration('charg_flag', 0);
    $eqt->setConfiguration('dischrg_flag', 0);
    switch ($name)
    {
      case 'VenusA' :
        $imgName = 'VenusA.png';
        break;
      case 'VenusC' :
      case 'VenusE' :
        $imgName = 'VenusCE.png';
        break;
      case 'VenusE 3.0':
        $imgName = 'VenusE3.png';
        break;
      case 'VenusD' :
        $imgName = 'VenusD.png';
        break;
      default :
        log::add(__CLASS__, 'warning', 'getImage : No match for '.$name.' => using default image');
        $imgName = 'default.png';
    }
    $eqt->setConfiguration('img', $imgName);
    $eqt->setCategory('energy','1');
    $eqt->setIsVisible(1);
    $eqt->setIsEnable(1);
    $eqt->save();
    return $eqt;
  }
  
  /* --- Methode statique pour MQTT --- */
  public static function handleMqttMessage($_datas) {
  
    //log::add(__CLASS__, 'debug', "HandleMqttMessage");
    //log::add(__CLASS__, 'debug', json_encode($_datas));
    if (isset($_datas[config::byKey('topic', __CLASS__, 'marstek')])) {
      $devices = $_datas[config::byKey('topic', __CLASS__, 'marstek')]['device'];
      $status = $_datas[config::byKey('topic', __CLASS__, 'marstek')]['status'];
  	}
    else {
      log::add(__CLASS__, 'error', 'handleMqttMessage : Unexepected topic - ignored');
      return;
    }
    
    // Traitement du topic device
    if (isset($devices))
    {  
      foreach($devices as $device => $param)
      {
        //log::add(__CLASS__,'debug', "Device Info ". $device ." => ".json_encode($param));
        $confsearch = array('src' => $device);
        $eqts = eqLogic::byTypeAndSearchConfiguration(__CLASS__, $confsearch);
        if (count($eqts) > 0)
        {
          // L'equipement existe, on l'extrait
          //log::add(__CLASS__,'debug', 'Device Info '. $device .' TROUVE');
          $eqt = $eqts[0];
        }
        else
        {
          // L'equipement n'existe pas, on le créé
          //log::add(__CLASS__,'debug', 'Device Info '. $device .' NON TROUVE');
          message::add(__CLASS__, 'Nouvelle batterie detectee : '.$device);
          $eqt = self::createDevice($device, $param['name']);
        }
        log::add(__CLASS__,'debug', 'Device Info : mise à jour de '. $device);
        $eqt->updateDevice($param);
      }
    }
   
    if (isset($status))
    {
     	foreach ($status as $device => $param)
        {
           	//log::add(__CLASS__,'debug', 'Device Status '.$device.' => '.json_encode($param));
        	$confsearch = array('src' => $device);
        	$eqts = eqLogic::byTypeAndSearchConfiguration(__CLASS__, $confsearch);
        	if (count($eqts) > 0)
        	{
          		// L'equipement existe, on met à jour ses parametres
          		//log::add(__CLASS__,'debug', 'Device status '. $device .' TROUVE');
          		$eqt = $eqts[0];
              	$remaining=$eqt->updateCommand($param);
              	if ($remaining)
                  $eqt->updateDevice($param);
            }
        	else
        	{
          		// L'equipement n'existe pas, on ne met rien à jour
          		log::add(__CLASS__,'warning', 'Device status : Device='. $device .' Does not exists');
        	}
        }
    }
  }
  
  /* ----- Methodes de classe perso ----- */
  public function updateDevice($param)
  {
    //log::add(__CLASS__, 'debug', 'updateDevice : '.$this->getName().' => ' .json_encode($param));
    foreach($param as $key => $value)
    {
      //log::add(__CLASS__, 'debug', 'updateDevice : Traitement clé '.$key.'=>'.$value);
      $curval = $this->getConfiguration($key,'N/A');
      //log::add(__CLASS__, 'debug', 'updateDevice : valeur actuelle : '.$curval);
      if (($curval != 'N/A') && ($curval != $value))
      {
        log::add(__CLASS__, 'debug', 'updateDevice : màj parametre : '.$key.' = '.$curval.'=>'.$value);
        $this->setConfiguration($key, $value);
      }
      else
      {
        if ($curval == 'N/A')
          log::add(__CLASS__, 'debug', 'updateDevice : parametre '.$key.'=>'.$value.' ignoré');
        else
          log::add(__CLASS__, 'debug', 'updateDevice : parametre '.$key.'=>'.$value.' inchangé ('.$value.'='.$curval.')');
      }
    }
    $this->save();
  }
  
  public function createCommand()
  {
    //log::add(__CLASS__,'debug', '>> Création des commandes pour la batterie '.$this->getHumanName()); 
  	$hasPV = ($this->getConfiguration('name') == "VenusD");
    $order = 0;
    
    // Commande info 'mode'
    $cmd = $this->getCmd(null, 'mode');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Mode', __FILE__));
      $cmd->setLogicalId('mode');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('string');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setDisplay('showNameOndashboard', 0);
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setTemplate('dashboard', 'marstekmqtt::String_Default');
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event('N/A'); // Initialisation à N/A
    $order++;
    
    // Commande action AUTO
    $cmd = $this->getCmd(null, 'Auto');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();
      $cmd->setLogicalId('Auto');
      $cmd->setName(__('Auto', __FILE__));
    }
    $cmd->setIsVisible(1);
    $cmd->setType('action');
    $cmd->setSubType('other');
    $cmd->setOrder($order);
    $cmd->setEqLogic_id($this->getId());
    $cmd->save();
    $order++;
    
    // Commande action AI
    $cmd = $this->getCmd(null, 'AI');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();
      $cmd->setLogicalId('AI');
      $cmd->setName(__('AI', __FILE__));
    }
    $cmd->setIsVisible(1);
    $cmd->setType('action');
    $cmd->setSubType('other');
    $cmd->setOrder($order);
    $cmd->setEqLogic_id($this->getId());
    $cmd->save();
    $order++;
    
    // Commande action Manual
    $cmd = $this->getCmd(null, 'Manual');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();
      $cmd->setLogicalId('Manual');
      $cmd->setName(__('Manual', __FILE__));
    }
    $cmd->setIsVisible(1);
    $cmd->setType('action');
    $cmd->setSubType('other');
    $cmd->setOrder($order);
    $cmd->setEqLogic_id($this->getId());
    $cmd->save();
    $order++;
    
    // Commande action Pässive
    $cmd = $this->getCmd(null, 'Passive');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();
      $cmd->setLogicalId('Passive');
      $cmd->setName(__('Passive', __FILE__));
    }
    $cmd->setIsVisible(1);
    $cmd->setType('action');
    $cmd->setSubType('other');
    $cmd->setOrder($order);
    $cmd->setEqLogic_id($this->getId());
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->save();
    $order++;
    
    // Commande info 'mode_power'
    //$cmd = $this->getCmd(null, 'mode_power');
    //if (!is_object($cmd)) {
    //  $cmd = new marstekmqttCmd();  
    //  $cmd->setName(__('Mode Power', __FILE__));
    //  $cmd->setLogicalId('mode_power');
    //}
    //$cmd->setIsVisible(0);
    //$cmd->setType('info');
    //$cmd->setSubType('numeric');
    //$cmd->setGeneric_type('POWER');
    //$cmd->setEqLogic_id($this->getId());
    //$cmd->setUnite('W');
    //$cmd->setConfiguration('minValue', -2500);
    //$cmd->setConfiguration('maxValue', 2500);
    //$cmd->setOrder($order);
  	//$cmd->setEqLogic_id($this->getId());
    //$cmd->save();
    //$cmd->event(0); // intialisation à 0
    //$modePowerId = $cmd->getId();
    //$order++;
    
    // commande action set_mode_power
    $cmd = $this->getCmd(null, 'set_mode_power');
    if (!is_object($cmd))
    {
      $cmd = new marstekmqttCmd();
      $cmd->setName(__('Mode Power', __FILE__));
      $cmd->setLogicalId('set_mode_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('action');
    $cmd->setSubType('slider');
    $cmd->setTemplate('dashboard', 'button');
    $cmd->setConfiguration('minValue', -2500);
    $cmd->setConfiguration('maxValue', 2500);
    $cmd->setConfiguration('step', 1);
    $arr = $cmd->getDisplay('parameters');
    log::add(__CLASS__,'debug', 'CreateCommand : param slider : '.json_decode($arr)); 
    $arr = array ('step' => '1');
    $cmd->setDisplay('parameters', $arr);
    $cmd->setDisplay('showNameOndashboard', 1);
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->setEqLogic_id($this->getId());
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // Commande info 'bat_soc'
    $cmd = $this->getCmd(null, 'bat_soc');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('SOC', __FILE__));
      $cmd->setLogicalId('bat_soc');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('%');
    $cmd->setTemplate('dashboard', 'marstekmqtt::Num_Bat_SOC_SOH');
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // Initialisation à 0%
    $order++;
    
    // Commande info 'bat_soh' ==> Calculé
    $cmd = $this->getCmd(null, 'bat_soh');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('SOH', __FILE__));
      $cmd->setLogicalId('bat_soh');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('%');
    $cmd->setTemplate('dashboard', 'marstekmqtt::Num_Bat_SOC_SOH');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(100); // intialisation à 100%
    $order++;
    
    // commande info On_grid_power
    $cmd = $this->getCmd(null, 'ongrid_power');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('OnGrid Power', __FILE__));
      $cmd->setLogicalId('ongrid_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('POWER');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('W');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info Off_grid_power
    $cmd = $this->getCmd(null, 'offgrid_power');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('OffGrid Power', __FILE__));
      $cmd->setLogicalId('offgrid_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('POWER');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('W');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info Bat_capacity
    $cmd = $this->getCmd(null, 'bat_capacity');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Battery Capacity', __FILE__));
      $cmd->setLogicalId('bat_capacity');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('PRODUCTION');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('Wh');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info bat_state ==> Calculé
    $cmd = $this->getCmd(null, 'bat_state');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('State', __FILE__));
      $cmd->setLogicalId('bat_state');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('string');
    $cmd->setTemplate('dashboard', 'marstekmqtt::String_Default');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event('Idle'); // Initialiastion à Idle
    $order++;
    
    // Commande info 'bat_temp'
    $cmd = $this->getCmd(null, 'bat_temp');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Temperature', __FILE__));
      $cmd->setLogicalId('bat_temp');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('TEMPERATURE');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('°C');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info ct_state
    $cmd = $this->getCmd(null, 'ct_state');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('CT State', __FILE__));
      $cmd->setLogicalId('ct_state');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('binary');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setTemplate('dashboard', 'marstekmqtt::Bin_Grey_Green');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(false); // intialisation à 0
    $order++;
    
    // commande info a_power
    $cmd = $this->getCmd(null, 'a_power');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('A Power', __FILE__));
      $cmd->setLogicalId('a_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('POWER');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('W');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info b_power
    $cmd = $this->getCmd(null, 'b_power');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('B Power', __FILE__));
      $cmd->setLogicalId('b_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('POWER');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('W');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info c_power
    $cmd = $this->getCmd(null, 'c_power');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('C Power', __FILE__));
      $cmd->setLogicalId('c_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('POWER');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('W');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info total_power
    $cmd = $this->getCmd(null, 'total_power');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Total Power', __FILE__));
      $cmd->setLogicalId('total_power');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('POWER');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('W');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    if ($hasPV)
    {
      //pv_power pv_voltage pv_current
    }
    
    // commande info total_grid_output_energy
    $cmd = $this->getCmd(null, 'total_grid_output_energy');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Total Grid Export Energy', __FILE__));
      $cmd->setLogicalId('total_grid_output_energy');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('PRODUCTION');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('Wh');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info total_grid_output_energy
    $cmd = $this->getCmd(null, 'total_grid_input_energy');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Total Grid Import Energy', __FILE__));
      $cmd->setLogicalId('total_grid_input_energy');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('CONSUMPTION');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('Wh');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
    
    // commande info total_load_energy
    $cmd = $this->getCmd(null, 'total_load_energy');
    if (!is_object($cmd)) {
      $cmd = new marstekmqttCmd();  
      $cmd->setName(__('Total load energy consumed', __FILE__));
      $cmd->setLogicalId('total_load_energy');
    }
    $cmd->setIsVisible(1);
    $cmd->setType('info');
    $cmd->setSubType('numeric');
    $cmd->setGeneric_type('CONSUMPTION');
    $cmd->setEqLogic_id($this->getId());
    $cmd->setUnite('Wh');
    $cmd->setTemplate('dashboard', 'core::badge');
    $cmd->setDisplay('forceReturnLineAfter', 1);
    $cmd->setOrder($order);
    $cmd->save();
    $cmd->event(0); // intialisation à 0
    $order++;
  }
  
  public function processState()
  {
    $state = 'Idle';
    $cmdongrid = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'ongrid_power');
    $cmdoffgrid = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'offgrid_power');
    $cmdState = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'bat_state');
    $ongridval = $cmdongrid->execCmd();
    $offgridval = $cmdoffgrid->execCmd();
    
    if ($ongridval == 0)
    {
      if ($offgridval != 0)
      {
        $state = "Passthrough";
      }
      else
      {
        $state = "Idle";
      }
    }
    elseif ($ongridval < 0)
    {
      $state = "Charging";
    }
    else
    {
      $state = "Discharging";
    }
    
    $curState = $cmdState->execCmd();
    if ($state != $curState)
    {
      //log::add(__CLASS__, 'debug', 'processState : mise à jour => '.$state);
      $cmdState->event($state);
    }
    //else
      //log::add(__CLASS__, 'debug', 'processState : inchangé');
  }
  
  public function processSOH()
  {
    $rated = $this->getConfiguration('rated_capacity');
    if ($rated != 'x')
    {
      $cmdongrid = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'ongrid_power');
      $ongridval = $cmdongrid->execCmd();
      $cmdcap = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'bat_capacity');
      $capval = $cmdcap->execCmd();
      $cmdSOC = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'bat_soc');
      $valSOC = $cmdSOC->execCmd();
      if (($valSOC == 100) & ($ongridval == 0))
      {
        
        $SOH = 100*($cmdcap/intval($rated));
        log::add(__CLASS__, 'debug', 'processSOH : mise à jour => '.strval($SOH));
        $cmdSOH = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), 'bat_soh');
        $cmdSOH->event($SOH);
      }
      else
        log::add(__CLASS__, 'debug', 'processSOH : conditons SOC/ongridpower non reunies');
    }
    else
      log::add(__CLASS__, 'debug', 'processSOH : rated cap non initialisé');
  }
  
  public function updateCommand($param)
  {
    //log::add(__CLASS__, 'debug', 'updateCommand : '.$this->getName().' => ' .json_encode($param));
    $nontraite = false;
    foreach($param as $key => $value)
    {
      //log::add(__CLASS__, 'debug', 'updateCommand : Traitement clé '.$key.'=>'.$value);
      $cmd = marstekmqttCmd::byEqLogicIdAndLogicalId($this->getId(), $key);
      if (is_object($cmd))
      {
        $curval = $cmd->execCmd();
        if ($curval != $value)
        {
          log::add(__CLASS__, 'debug', 'updateCommand : mise à jour commande '.$key.' : '.$curval.'=>'.$value);
          $cmd->event($value);
          if (($key='ongrid_power') or ($key='offgrid_power'))
            $this->processState();
          if (($key='ongrid_power') or ($key='bat_soc'))
            $this->processSOH();
        }
        else
        {
          log::add(__CLASS__, 'debug', 'updateCommand : commande '.$key.' inchangée ('.$curval.'='.$value.')');
        }
      }
      else
      {
        log::add(__CLASS__, 'debug', 'updateCommand : cle commande '.$key.' ignorée');
        $nontraite = true;
      }
    }
    return $nontraite;
  }
  
  
  /*     * *********************Méthodes d'instance************************* */

  // Fonction exécutée automatiquement avant la création de l'équipement
  public function preInsert()
  {
  }

  // Fonction exécutée automatiquement après la création de l'équipement
  public function postInsert()
  {
    //log::add(__CLASS__, 'debug', 'postInsert');
    $this->createCommand();
  }

  // Fonction exécutée automatiquement avant la mise à jour de l'équipement
  public function preUpdate()
  {
  }

  // Fonction exécutée automatiquement après la mise à jour de l'équipement
  public function postUpdate()
  {
  }

  // Fonction exécutée automatiquement avant la sauvegarde (création ou mise à jour) de l'équipement
  public function preSave()
  {
  }

  // Fonction exécutée automatiquement après la sauvegarde (création ou mise à jour) de l'équipement
  public function postSave()
  {
    //log::add(__CLASS__, 'debug', 'postSave');
  }

  // Fonction exécutée automatiquement avant la suppression de l'équipement
  public function preRemove()
  {
  }

  // Fonction exécutée automatiquement après la suppression de l'équipement
  public function postRemove()
  {
  }

  
  // returne l'image du device
  public function getImage()
  {
    $imgName = $this->getConfiguration('img','default.png');
    return 'plugins/marstekmqtt/data/img/devices/'.$imgName;
  }
  
  public static function templateWidget()
  {
    $return = array('info' => array('string' => array()));
    
    
    // Info Binaire Gris/Jaune
    $return['info']['binary']['Bin_Grey_Green'] = array
    (
      	'template' => 'tmplimg',
      	'replace' => array
      		(
                '#_img_light_on_#' => '<img class="img-responsive" src="plugins/marstekmqtt/data/img/widget/Status_Vert.png">',
                '#_img_dark_on_#'  => '<img class="img-responsive" src="plugins/marstekmqtt/data/img/widget/Status_Vert.png">',
                '#_img_light_off_#' => '<img class="img-responsive" src="plugins/marstekmqtt/data/img/widget/Status_Gris.png">',
                '#_img_dark_off_#'  => '<img class="img-responsive" src="plugins/marstekmqtt/data/img/widget/Status_Gris.png">',
              	'#_desktop_width_#' => '16'
            )
    );
    
    // Info Bat_SOC_SOH
    $return['info']['numeric']['Num_Bat_SOC_SOH'] = array
    (
    	'template' => 'tmplmultistate',
        'test' => array
      	(
        	array
            (
            	'operation' => '#value# < 20',
                'state_light' => '<p><font color="red" size="3pt">#value# #unite#</font></p>'
            ),
          	array
            (
                'operation' => '#value# >= 20 && #value# < 60',
                'state_light' => '<p><font color="orange" size="3pt">#value# #unite#</font></p>'
            ),
            array
            (
            	'operation' => '#value# >= 60',
                'state_light' => '<p><font color="green" size="3pt">#value# #unite#</font></p>'
            )
        )
    );
    
    $return['info']['string']['String_Default'] = array
    (
    	'template' => 'tmplmultistate',
        'test' => array
      	(
        	array
            (
            	'operation' => '1',
                'state_light' => '<p><font size="4.5pt">#value#</font></p>'
            )
        )
    );
    
    return $return;
  }

  /*     * **********************Getteur Setteur*************************** */
}
  
  

class marstekmqttCmd extends cmd {
  /*     * *************************Attributs****************************** */

  /*
  public static $_widgetPossibility = array();
  */

  /*     * ***********************Methode static*************************** */


  /*     * *********************Methode d'instance************************* */

  /*
  * Permet d'empêcher la suppression des commandes même si elles ne sont pas dans la nouvelle configuration de l'équipement envoyé en JS
  public function dontRemoveCmd() {
    return true;
  }
  */

  // Exécution d'une commande
  public function execute($_options = array())
  {
    log::add('marstekmqtt', 'debug', 'Execute');
    
    $eqLogic = $this->getEqLogic();
    
    if (is_object($eqLogic))
    {
      $src = $eqLogic->getConfiguration('src');
      $publish = true;
      log::add('marstekmqtt', 'debug', 'Execute : src='.$src);
      $command = $this->getLogicalId();
      $cmdSlider = cmd::byEqLogicIdAndLogicalId($eqLogic->getID(),'set_mode_power');
      $sliderValue = $cmdSlider->getConfiguration('lastCmdValue');
      log::add('marstekmqtt', 
               'debug',
               'Execute : src='.$src.' / command='.$command.' / ref slider='.$cmdSlider->getHumanName(). ' valeur = '.$sliderValue);
      
      switch ($command)
      {
        case 'Auto':
        case 'AI' :
          $topic_cmd = 'marstek/action/'.$src;
          $payload = '{"cmd":"'.$command.'"}';
          break;
        case 'Manual' :
        case 'Passive' :
          $topic_cmd = 'marstek/action/'.$src;
          $payload = '{"cmd":"'.$command.'", "power":'.$sliderValue.'}';
          break;
        default :
          $publish = false;
      }
      if ($publish)
      {
        log::add('marstekmqtt', 'debug', 'execute : publishing '.$topic_cmd.'=>'.$payload);
        mqtt2::publish($topic_cmd, $payload);
      }
    }
  }

  /*     * **********************Getteur Setteur*************************** */
}
