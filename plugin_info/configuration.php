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

require_once dirname(__FILE__) . '/../../../core/php/core.inc.php';
include_file('core', 'authentification', 'php');
if (!isConnect()) {
  include_file('desktop', '404', 'php');
  die();
}
?>
<form class="form-horizontal">
  <fieldset>
  
    <legend><i class="fas fa-play-circle"></i> {{Parametrage}}</legend>
  
    <div class="form-group">
  
  	  <!-- Plugin Version -->
	  <label class="col-md-2 control-label">{{Plugin version}}</label>
	  <div class="col-md-1">
        <?php
         echo '<span class="label label-success"> '. marstekmqtt::getPluginVersion() . '</span>';
        ?>
	  </div>
             
      <!-- API Version -->
	  <label class="col-md-2 control-label">{{API version}}</label>
	  <div class="col-md-1">
        <?php
          echo '<span class="label label-success"> '. marstekmqtt::getApiVersion() . '</span>';
        ?>
	  </div>
      
      <!-- Configuration Demon distant -->
      <label class="col-md-2 control-label">{{Demon distant}}
        <sup><i class="fas fa-question-circle tooltips" title="{{Pour debug uniquement}}"></i></sup>
      </label>
      <div class="col-md-1">
	    <input type="checkbox" class="configKey form-control" style="width:auto;" data-l1key="RemoteDemon" unchecked/>
	  </div>
          
    </div>
          
    <div class="form-group">
          
      <!-- Configuration du port API Marstek -->
      <label class="col-md-2 control-label">{{Port API Marstek}}
        <sup><i class="fas fa-question-circle tooltips" title="{{Renseignez le port UDP de l'API Marstek}}"></i></sup>
      </label>
      <div class="col-md-1">
        <input class="configKey form-control" data-l1key="apiPort" placeholder="30000"/>
      </div>
          
      <!-- confiuguration timeout -->
      <label class="col-md-2 control-label">{{Timeout requete API (s)}}
        <sup><i class="fas fa-question-circle tooltips" title="{{Renseignez le temps d'attente maximum pour une réponse à une requete API}}"></i></sup>
      </label>
      <div class="col-md-1">
        <input class="configKey form-control" data-l1key="apiTimeout" placeholder="5"/>
      </div>
          
      <!-- confiuguration retry -->
      <label class="col-md-2 control-label">{{Nb tentative requete API}}
        <sup><i class="fas fa-question-circle tooltips" title="{{Renseignez le nombre de tentatives successives pour une requete API}}"></i></sup>
      </label>
      <div class="col-md-1">
        <input class="configKey form-control" data-l1key="apiRetry" placeholder="3"/>
      </div>
          
      <!-- confiuguration periode -->
      <label class="col-md-2 control-label">{{Periode sondage (s)}}
        <sup><i class="fas fa-question-circle tooltips" title="{{Renseignez la periode de sondage des batteries}}"></i></sup>
      </label>
      <div class="col-md-1">
        <input class="configKey form-control" data-l1key="period" placeholder="10"/>
      </div>
          
    </div>
          
  </fieldset>
          
</form>
